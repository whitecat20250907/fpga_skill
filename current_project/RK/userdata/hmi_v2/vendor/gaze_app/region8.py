# encoding=utf-8
"""8x8 区域判定：停留投票 + 迟滞 + 置信度拒绝。

竞赛目标不是"精确像素坐标"，而是"8x8 = 64 个区域里选对那个"。
这两件事的判定标准完全不同：

- 回归任务看平均像素误差；
- 区域任务看命中率，而且**允许用时间换准确率**（人本来就要注视一会儿）。

因此在线判定不应该每帧直接输出坐标，而应该：

1. 在一个滑动窗口内对**格子编号**做多数投票（不是对坐标平均，
   坐标平均会被屏幕边缘的大误差带偏）；
2. 加迟滞：新格子必须连续确认若干帧才允许切换，避免光标在两格之间跳；
3. 置信度低于阈值时**保持不动**而不是猜——比赛里"不乱跳"比"偶尔猜中"重要。

参数默认值来自 mouse3 标定数据的离线仿真（见 README 里的实测表）。
"""

from __future__ import annotations

from collections import Counter, deque


def to_cell(x_norm: float, y_norm: float, grid: int = 8):
    """归一化坐标 -> (col, row)，越界自动夹到 0..grid-1。"""
    col = min(max(int(x_norm * grid), 0), grid - 1)
    row = min(max(int(y_norm * grid), 0), grid - 1)
    return col, row


class RegionDecider:
    """把逐帧坐标流收敛成一个稳定的 8x8 区域输出。

    window        : 多数投票窗口长度（帧）。30fps 下 12 帧 ≈ 0.4s。
    hysteresis    : 切换区域前需要连续确认的帧数。3 帧 ≈ 0.1s。
    min_confidence: 窗口内多数票占比低于该值时视为"不确定"，输出保持上一次。
    """

    def __init__(self, grid: int = 8, window: int = 12, hysteresis: int = 3,
                 min_confidence: float = 0.6):
        self.grid = grid
        self.window = window
        self.hysteresis = hysteresis
        self.min_confidence = min_confidence
        self.cells = deque(maxlen=window)
        self.current = None
        self.candidate = None
        self.candidate_run = 0
        self.confidence = 0.0

    def reset(self):
        self.cells.clear()
        self.current = None
        self.candidate = None
        self.candidate_run = 0
        self.confidence = 0.0

    def update(self, x_norm: float, y_norm: float):
        """喂入一帧归一化坐标，返回当前确认的区域 (col, row) 或 None。"""
        self.cells.append(to_cell(x_norm, y_norm, self.grid))
        if not self.cells:
            return self.current

        (majority, votes) = Counter(self.cells).most_common(1)[0]
        self.confidence = votes / len(self.cells)

        if majority == self.current:
            self.candidate, self.candidate_run = None, 0
            return self.current

        if majority == self.candidate:
            self.candidate_run += 1
        else:
            self.candidate, self.candidate_run = majority, 1

        if self.candidate_run >= self.hysteresis and self.confidence >= self.min_confidence:
            self.current = self.candidate
            self.candidate, self.candidate_run = None, 0
        return self.current

    @property
    def decided(self) -> bool:
        return self.current is not None and self.confidence >= self.min_confidence


def dwell_cell_vote(pred_cells, target_cell, window: int = 12):
    """离线评测用：对一整段注视做滑窗多数投票，返回 (命中率, 覆盖率)。

    pred_cells  : [(col, row), ...] 按时间排序
    target_cell : (col, row) 真值
    覆盖率指置信度达标的窗口占比，便于评估"不确定时不输出"的代价。
    """
    if len(pred_cells) < window:
        window = max(1, len(pred_cells))
    hits, decided = [], []
    for start in range(0, max(1, len(pred_cells) - window + 1)):
        chunk = pred_cells[start:start + window]
        if not chunk:
            continue
        (majority, votes) = Counter(chunk).most_common(1)[0]
        conf = votes / len(chunk)
        decided.append(conf >= 0.6)
        hits.append(majority == target_cell)
    if not hits:
        return 0.0, 0.0
    hits_arr = [h for h, d in zip(hits, decided) if d]
    return (sum(hits_arr) / len(hits_arr) if hits_arr else 0.0,
            sum(decided) / len(decided))
