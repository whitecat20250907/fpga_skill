"""Head geometry: pose estimation and rotation-normalised eye ROI.

为什么需要这个模块
------------------
当前链路里有两个缺口，属于「技术路线」层面而不是调参层面：

1. **头部姿态从未被计算**。运行时只把 MGazeNet 的 258 维特征交给标定器，
   而标定器无法区分「眼球在头内转动」和「头整体在动」——这两者产生
   的特征变化是混在一起的。MediaPipe 的 468 个 landmark 携带足够多的
   空间结构，可以直接恢复 pitch / yaw / roll。

2. **眼睛 ROI 是轴对齐矩形**（见 `MediaPipeFaceAlignment.py:367-386`）。
   那段代码用两个内眼角的 x 坐标直接构造左右边界，隐含「正脸」假设：
   头部 yaw 偏转时两眼角 x 顺序可能反转、矩形宽度塌陷；头部 roll 时
   眼睛在 patch 内是倾斜的，与模型训练时的正向眼睛外观不一致。
   下面的 `rotation_normalised_eye_rect` 改为以眼角连线为基准做相似
   变换（旋转 + 缩放），把眼睛统一摆正后再送进网络。

坐标系约定（OpenCV 相机系：x 向右、y 向下、z 指向场景）
    pitch  绕 x 轴 —— 抬头 / 低头
    yaw    绕 y 轴 —— 左转 / 右转
    roll   绕 z 轴 —— 歪头

只依赖 numpy + OpenCV，便于移植到 RK3576。没有引入任何训练/标定依赖，
所以可以安全地作为独立模块试用，不影响现有启动流程。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np

# --------------------------------------------------------------------------
# 3D 参考点：用一个通用人脸模型，配合 MediaPipe 的 6 个 landmark 做 solvePnP。
# 单位是毫米级的近似值，只需要比例正确——绝对尺度只影响 tvec（距离），
# 不影响我们真正要的旋转角。
# --------------------------------------------------------------------------
NOSE_TIP = 1
CHIN = 199
EYE_OUTER_IMAGE_LEFT = 33      # 被试的右眼外角，出现在画面左侧
EYE_OUTER_IMAGE_RIGHT = 263    # 被试的左眼外角，出现在画面右侧
MOUTH_IMAGE_LEFT = 61
MOUTH_IMAGE_RIGHT = 291

REFERENCE_LANDMARKS: tuple[int, ...] = (
    NOSE_TIP, CHIN, EYE_OUTER_IMAGE_LEFT,
    EYE_OUTER_IMAGE_RIGHT, MOUTH_IMAGE_LEFT, MOUTH_IMAGE_RIGHT,
)

REFERENCE_MODEL_3D = np.array([
    (0.0, 0.0, 0.0),           # 鼻尖
    (0.0, -330.0, -65.0),      # 下巴
    (-225.0, 170.0, -135.0),   # 画面左侧眼外角
    (225.0, 170.0, -135.0),    # 画面右侧眼外角
    (-150.0, -150.0, -125.0),  # 画面左侧嘴角
    (150.0, -150.0, -125.0),   # 画面右侧嘴角
], dtype=np.float64)


@dataclass
class HeadPose:
    """单帧头部姿态。角度单位为度。"""

    pitch_deg: float
    yaw_deg: float
    roll_deg: float
    rotation: np.ndarray
    rvec: np.ndarray
    tvec: np.ndarray

    def as_features(self) -> np.ndarray:
        """拼到标定器输入尾部用的 3 维向量。"""
        return np.array([self.pitch_deg, self.yaw_deg, self.roll_deg], dtype=np.float32)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (f"HeadPose(pitch={self.pitch_deg:+.1f}°, "
                f"yaw={self.yaw_deg:+.1f}°, roll={self.roll_deg:+.1f}°)")


def _rotation_to_euler(rotation: np.ndarray) -> tuple[float, float, float]:
    """从旋转矩阵提取 XYZ 欧拉角，返回 (pitch, yaw, roll)，单位度。"""
    sy = math.hypot(rotation[0, 0], rotation[1, 0])
    if sy > 1e-6:
        pitch = math.atan2(rotation[2, 1], rotation[2, 2])
        yaw = math.atan2(-rotation[2, 0], sy)
        roll = math.atan2(rotation[1, 0], rotation[0, 0])
    else:  # 万向节死锁
        pitch = math.atan2(-rotation[1, 2], rotation[1, 1])
        yaw = math.atan2(-rotation[2, 0], sy)
        roll = 0.0
    return math.degrees(pitch), math.degrees(yaw), math.degrees(roll)


class HeadPoseEstimator:
    """从 MediaPipe FaceMesh 的 468 点恢复头部姿态。

    相机内参用帧宽做近似焦距。这对本项目是够用的——我们关心的是**角度
    的相对变化**（判断头有没有动、动了多少），而不是绝对的三维重建精度。
    如果之后要接真实内参，把 camera_matrix 传进来即可。
    """

    def __init__(self, image_size: tuple[int, int] | None = None,
                 camera_matrix: np.ndarray | None = None,
                 dist_coeffs: np.ndarray | None = None) -> None:
        self.image_size = image_size
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs if dist_coeffs is not None else np.zeros((4, 1))

    def _camera_matrix(self, image_size: tuple[int, int]) -> np.ndarray:
        if self.camera_matrix is not None:
            return self.camera_matrix
        width, height = image_size
        focal = float(max(width, height))
        return np.array([[focal, 0.0, width / 2.0],
                         [0.0, focal, height / 2.0],
                         [0.0, 0.0, 1.0]], dtype=np.float64)

    def solve(self, landmarks: np.ndarray,
              image_size: tuple[int, int] | None = None) -> HeadPose | None:
        """landmarks: (>=292, 3) 的数组，前两列为像素坐标。

        失败（点缺失、退化几何、solvePnP 不收敛）时返回 None，而不是抛异常，
        这样调用方可以直接跳过该帧。
        """
        points = np.asarray(landmarks, dtype=np.float64)
        if points.ndim != 2 or points.shape[0] <= max(REFERENCE_LANDMARKS):
            return None

        size = image_size or self.image_size
        if size is None:
            # 没有显式给尺寸时，用 landmark 的包围盒粗略推断，仍可得到相对角度
            span = np.ptp(points[:, :2], axis=0)
            size = (int(span[0] * 1.6) or 640, int(span[1] * 2.0) or 480)

        image_points = points[list(REFERENCE_LANDMARKS), :2].astype(np.float64)
        if not np.isfinite(image_points).all():
            return None

        try:
            ok, rvec, tvec = cv2.solvePnP(
                REFERENCE_MODEL_3D, image_points, self._camera_matrix(size),
                self.dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE)
        except cv2.error:
            return None
        if not ok:
            return None

        rotation, _ = cv2.Rodrigues(rvec)
        pitch, yaw, roll = _rotation_to_euler(rotation)
        return HeadPose(pitch, yaw, roll, rotation, rvec.reshape(3), tvec.reshape(3))

    def solve_from_face_info(self, face_info) -> HeadPose | None:
        """便捷入口：直接吃 GazeFollower 的 FaceInfo（读 face_landmarks / img_w / img_h）。"""
        landmarks = getattr(face_info, "face_landmarks", None)
        if landmarks is None:
            return None
        size = None
        width, height = getattr(face_info, "img_w", 0), getattr(face_info, "img_h", 0)
        if width and height:
            size = (int(width), int(height))
        return self.solve(landmarks, size)


# --------------------------------------------------------------------------
# 旋转归一化的眼睛 ROI
# --------------------------------------------------------------------------
# 左眼（画面左侧）：33 = 外眼角，133 = 内眼角
# 右眼（画面右侧）：362 = 内眼角，263 = 外眼角
# 两眼的「外眼角 -> 内眼角」向量方向相反，所以左右眼分开给参数。
LEFT_EYE_CORNERS = (EYE_OUTER_IMAGE_LEFT, 133)
RIGHT_EYE_CORNERS = (362, EYE_OUTER_IMAGE_RIGHT)


def eye_corner_angle(landmarks: np.ndarray, outer_idx: int, inner_idx: int) -> float:
    """眼角连线相对水平方向的角度（度）。头部 roll 时这个值会明显偏离 0。"""
    points = np.asarray(landmarks, dtype=np.float64)
    outer = points[outer_idx, :2]
    inner = points[inner_idx, :2]
    delta = inner - outer
    return math.degrees(math.atan2(delta[1], delta[0]))


def rotation_normalised_eye_rect(
    landmarks: np.ndarray,
    outer_idx: int,
    inner_idx: int,
    out_size: int = 112,
    corner_span: float = 0.70,
) -> np.ndarray | None:
    """返回一个 2x3 仿射矩阵，把原图映射到「摆正后」的眼睛 patch。

    变换由眼角连线决定：
      * 旋转到水平 —— 抵消 roll
      * 缩放到固定尺度 —— 抵消人脸远近

    `corner_span` 是两个眼角占输出 patch 宽度的比例。0.70 是照现有实现的
    几何反推的：原代码把眼角距 D 外面各加 20% D 的 padding，得到框宽 1.4D，
    即眼角距占 70%。保持这个比例可以让眼睛在 patch 里的占比和现在接近，
    减少对模型输入分布的改变。
    """
    points = np.asarray(landmarks, dtype=np.float64)
    if points.ndim != 2 or points.shape[0] <= max(outer_idx, inner_idx):
        return None

    outer = points[outer_idx, :2]
    inner = points[inner_idx, :2]
    if not (np.isfinite(outer).all() and np.isfinite(inner).all()):
        return None

    centre = (outer + inner) / 2.0
    span = float(np.linalg.norm(inner - outer))
    if span < 1e-3:
        return None

    angle = math.degrees(math.atan2((inner - outer)[1], (inner - outer)[0]))
    scale = out_size * corner_span / span

    matrix = cv2.getRotationMatrix2D((float(centre[0]), float(centre[1])), angle, scale)
    # 把眼角中点平移到输出 patch 的正中心
    matrix[0, 2] += out_size / 2.0 - centre[0]
    matrix[1, 2] += out_size / 2.0 - centre[1]
    return matrix


def warp_eye_patch(image: np.ndarray, matrix: np.ndarray, out_size: int = 112) -> np.ndarray | None:
    """按仿射矩阵裁出眼睛 patch。越界部分用边缘像素填充，不引入黑边。"""
    if matrix is None:
        return None
    return cv2.warpAffine(image, matrix, (out_size, out_size),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def rotation_normalised_eyes(landmarks: np.ndarray, image: np.ndarray,
                             out_size: int = 112) -> tuple[np.ndarray | None, np.ndarray | None]:
    """一次拿到左右两只摆正的眼睛 patch（和现有流程一样，右眼水平翻转）。"""
    left_matrix = rotation_normalised_eye_rect(landmarks, out_size=out_size,
                                               *LEFT_EYE_CORNERS)
    right_matrix = rotation_normalised_eye_rect(landmarks, out_size=out_size,
                                                *RIGHT_EYE_CORNERS)
    left = warp_eye_patch(image, left_matrix, out_size)
    right = warp_eye_patch(image, right_matrix, out_size)
    if right is not None:
        right = cv2.flip(right, 1)
    return left, right


# --------------------------------------------------------------------------
# 自检：不依赖任何采集数据，用几何往返验证实现是否正确
# --------------------------------------------------------------------------
def euler_to_rotation(pitch_deg: float, yaw_deg: float, roll_deg: float) -> np.ndarray:
    """按 R = Rz(roll)·Ry(yaw)·Rx(pitch) 组合成旋转矩阵。

    这个约定必须和 `_rotation_to_euler` 的提取方式一致，否则多轴同时旋转时
    会出现几度的系统性偏差。
    """
    a, b, c = (math.radians(v) for v in (pitch_deg, yaw_deg, roll_deg))
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return rz @ ry @ rx


def _self_test() -> None:
    print("=" * 68)
    print("1) 头部姿态 —— 投影/反解往返测试")
    print("=" * 68)
    size = (640, 480)
    estimator = HeadPoseEstimator(image_size=size)
    camera = estimator._camera_matrix(size)
    distance = np.array([0.0, 0.0, 600.0])

    ok = True
    for pitch_true, yaw_true, roll_true in [
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (0.0, 15.0, 0.0),
        (0.0, 0.0, 8.0),
        (-12.0, -20.0, -6.0),
    ]:
        rotation_true = euler_to_rotation(pitch_true, yaw_true, roll_true)
        rvec_true, _ = cv2.Rodrigues(rotation_true)
        rvec_true = rvec_true.reshape(3)
        projected, _ = cv2.projectPoints(REFERENCE_MODEL_3D, rvec_true, distance, camera, None)

        landmarks = np.zeros((468, 3), dtype=np.float64)
        for slot, landmark_id in enumerate(REFERENCE_LANDMARKS):
            landmarks[landmark_id, :2] = projected[slot, 0, :]

        pose = estimator.solve(landmarks)
        if pose is None:
            print(f"   真值({pitch_true:+6.1f},{yaw_true:+6.1f},{roll_true:+6.1f}) -> 求解失败")
            ok = False
            continue

        error = max(abs(pose.pitch_deg - pitch_true),
                    abs(pose.yaw_deg - yaw_true),
                    abs(pose.roll_deg - roll_true))
        flag = "OK " if error < 0.5 else "FAIL"
        if error >= 0.5:
            ok = False
        print(f"   {flag} 真值({pitch_true:+6.1f},{yaw_true:+6.1f},{roll_true:+6.1f})"
              f"  ->  解出({pose.pitch_deg:+6.1f},{pose.yaw_deg:+6.1f},{pose.roll_deg:+6.1f})"
              f"  最大误差 {error:.3f}°")

    print()
    print("=" * 68)
    print("2) 眼睛 ROI —— 摆正效果")
    print("=" * 68)

    # 合成一只 roll 了 20° 的眼睛，验证归一化后眼角回到水平
    landmarks = np.zeros((468, 3), dtype=np.float64)
    landmarks[EYE_OUTER_IMAGE_LEFT] = (180.0, 200.0, 0.0)
    landmarks[133] = (240.0, 200.0, 0.0)  # 正脸时水平
    before = eye_corner_angle(landmarks, *LEFT_EYE_CORNERS)

    # 把这只眼睛整体旋转 20°
    theta = math.radians(20.0)
    rot = np.array([[math.cos(theta), -math.sin(theta)],
                    [math.sin(theta), math.cos(theta)]])
    pivot = np.array([210.0, 200.0])
    for idx in LEFT_EYE_CORNERS:
        landmarks[idx, :2] = rot @ (landmarks[idx, :2] - pivot) + pivot
    rolled = eye_corner_angle(landmarks, *LEFT_EYE_CORNERS)

    matrix = rotation_normalised_eye_rect(landmarks, *LEFT_EYE_CORNERS)
    # 把两个眼角重新映射一遍，看它们是否落在同一水平线上
    def _apply(point: np.ndarray) -> np.ndarray:
        return matrix[:, :2] @ point + matrix[:, 2]

    outer_out = _apply(landmarks[EYE_OUTER_IMAGE_LEFT, :2])
    inner_out = _apply(landmarks[133, :2])
    residual = math.degrees(math.atan2((inner_out - outer_out)[1],
                                       (inner_out - outer_out)[0]))
    span_ratio = float(np.linalg.norm(inner_out - outer_out)) / 112.0

    print(f"   正脸时眼角角度      = {before:+.2f}°")
    print(f"   roll 20° 后角度     = {rolled:+.2f}°")
    print(f"   归一化后残留角度    = {residual:+.4f}°   (期望 ≈ 0)")
    print(f"   眼角距占 patch 宽度 = {span_ratio:.3f}      (期望 ≈ 0.70)")
    if abs(residual) > 0.01 or not (0.69 < span_ratio < 0.71):
        ok = False
        print("   FAIL")
    else:
        print("   OK")

    print()
    print("=" * 68)
    print("总体:", "全部通过" if ok else "存在失败项")
    print("=" * 68)


if __name__ == "__main__":
    _self_test()
