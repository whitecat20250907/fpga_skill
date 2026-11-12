# encoding=utf-8
"""标准化 Ridge + 逐轴单调校正（isotonic / PAVA）标定器。

只依赖 numpy，不依赖 scikit-learn，便于移植到嵌入式（RK3576）。

为什么需要它（实测结论，基于 mouse3/data/*/calibration_01/samples.npz 的留一点交叉验证）：

1. 现用的 SVR(rbf, C=1, gamma=5e-3) 在 390 样本 × 258 维下严重过拟合，
   8x8 区域命中率只有 0%–10%（随机基线 1.6%）。
2. 换成标准化 Ridge 后升到 20%–34%。
3. 再叠加逐轴单调校正后升到 37%–53%（单帧）、46%–62%（逐点多数投票）。

单调校正有效的原因：MGazeNet 输出的 258 维特征到屏幕坐标的映射被严重压缩
（整屏只变化约 3.7cm × 5.1cm），线性回归的输出动态范围不足，导致屏幕边缘
被系统性拉向中心。isotonic 回归能把这层单调压缩掰回来。

接口与 GazeFollower.calibration.Calibration 保持一致，可直接替换 SVRCalibration。
"""

from __future__ import annotations

import numpy as np

from gazefollower.calibration.Calibration import Calibration
from gazefollower.logger import Log


class Monotonic1D:
    """一维单调回归（PAVA），带线性插值预测。

    fit(x, y): 按 x 排序后做 pool-adjacent-violators，得到单调不减的阶梯，
               再合并重复 x 取均值，保存 (xs, ys) 供插值。
    predict(x): 线性插值，超出范围时取端点值（clip）。
    """

    def __init__(self):
        self.xs = None
        self.ys = None
        self.fitted = False

    @staticmethod
    def _pava(y: np.ndarray) -> np.ndarray:
        n = len(y)
        vals, wts, cnts = [], [], []
        for i in range(n):
            v = float(y[i])
            w = 1.0
            c = 1
            while vals and vals[-1] > v:
                vp = vals.pop()
                wp = wts.pop()
                cp = cnts.pop()
                v = (vp * wp + v * w) / (wp + w)
                w = wp + w
                c = cp + c
            vals.append(v)
            wts.append(w)
            cnts.append(c)
        out = np.empty(n, dtype=np.float64)
        pos = 0
        for v, c in zip(vals, cnts):
            out[pos:pos + c] = v
            pos += c
        return out

    def fit(self, x: np.ndarray, y: np.ndarray):
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if len(x) < 2 or np.ptp(x) <= 0:
            self.fitted = False
            return self
        order = np.argsort(x, kind="mergesort")
        xs, ys = x[order], y[order]
        fitted = self._pava(ys)
        # 合并重复 x（取均值），保持单调
        ux, inv = np.unique(xs, return_inverse=True)
        sums = np.bincount(inv, weights=fitted)
        cnts = np.bincount(inv)
        uy = sums / cnts
        uy = np.maximum.accumulate(uy)  # 保险：单调不减
        self.xs, self.ys = ux, uy
        self.fitted = len(ux) >= 2
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        if not self.fitted:
            return x
        return np.interp(x, self.xs, self.ys)


class RidgeIsotonicCalibration(Calibration):
    """标准化 Ridge 回归 + 逐轴单调校正。

    参数
    ----
    alpha : Ridge 正则强度（在标准化后的特征上）。
    use_isotonic : 是否启用逐轴单调校正。关掉即退化为"标准化 Ridge"。
    standardize : 是否对特征做 z-score 标准化。258 维特征量纲差异极大，
                  不标准化时正则项会被个别大尺度维度主导。
    """

    def __init__(self, alpha: float = 1.0, use_isotonic: bool = True,
                 standardize: bool = True):
        super().__init__()
        self.alpha = float(alpha)
        self.use_isotonic = bool(use_isotonic)
        self.standardize = bool(standardize)
        self.weights = None          # (d+1, 2)，第 0 行为偏置
        self.feature_mean = None
        self.feature_std = None
        self.iso_x = Monotonic1D()
        self.iso_y = Monotonic1D()

    # ---- 内部工具 ----
    def _design(self, features: np.ndarray) -> np.ndarray:
        features = np.asarray(features, dtype=np.float64)
        if features.ndim == 1:
            features = features.reshape(1, -1)
        if self.standardize and self.feature_mean is not None:
            features = (features - self.feature_mean) / self.feature_std
        return np.c_[np.ones((features.shape[0], 1)), features]

    # ---- Calibration 接口 ----
    def calibrate(self, features, labels, ids=None):
        features = np.asarray(features, dtype=np.float64)
        labels = np.asarray(labels, dtype=np.float64)
        if features.ndim == 1:
            features = features.reshape(1, -1)

        if self.standardize:
            mu = features.mean(axis=0)
            sd = features.std(axis=0)
            sd[sd < 1e-8] = 1.0
            self.feature_mean, self.feature_std = mu, sd
        else:
            self.feature_mean = np.zeros(features.shape[1])
            self.feature_std = np.ones(features.shape[1])

        X = self._design(features)
        d = X.shape[1]
        I = np.eye(d)
        I[0, 0] = 0.0  # 不正则化偏置
        try:
            XtX = X.T @ X
            XtY = X.T @ labels
            self.weights = np.linalg.solve(XtX + self.alpha * I, XtY)
            self.has_calibrated = True
        except np.linalg.LinAlgError as exc:
            self.has_calibrated = False
            Log.e(f"Ridge solve failed: {exc}")
            return False, float("inf"), None

        raw = X @ self.weights
        if self.use_isotonic:
            # 单调校正在训练集上拟合（防止过拟合：PAVA 的拟合自由度远低于线性模型）
            self.iso_x.fit(raw[:, 0], labels[:, 0])
            self.iso_y.fit(raw[:, 1], labels[:, 1])
            predictions = np.c_[self.iso_x.predict(raw[:, 0]),
                                self.iso_y.predict(raw[:, 1])]
        else:
            self.iso_x, self.iso_y = Monotonic1D(), Monotonic1D()
            predictions = raw

        error = float(np.mean(np.linalg.norm(labels - predictions, axis=1)))
        Log.d(f"RidgeIso calibration done, mean normalized error = {error:.4f}")
        return True, error, predictions

    def predict(self, features, estimated_coordinate):
        if not self.has_calibrated:
            return False, estimated_coordinate
        raw = self._design(np.asarray(features, dtype=np.float64)) @ self.weights
        x = float(self.iso_x.predict(raw[0, 0])) if self.use_isotonic else float(raw[0, 0])
        y = float(self.iso_y.predict(raw[0, 1])) if self.use_isotonic else float(raw[0, 1])
        return True, (x, y)

    # ---- 持久化（可选，用于复现与嵌入式导出）----
    def export(self) -> dict:
        return {
            "alpha": self.alpha,
            "use_isotonic": self.use_isotonic,
            "standardize": self.standardize,
            "weights": self.weights,
            "feature_mean": self.feature_mean,
            "feature_std": self.feature_std,
            "iso_x": (self.iso_x.xs, self.iso_x.ys),
            "iso_y": (self.iso_y.xs, self.iso_y.ys),
        }

    def save_model(self) -> bool:
        # 与 SVR 不同，本标定器不走 XML；持久化由调用方用 np.savez 完成。
        return self.weights is not None

    def release(self):
        pass
