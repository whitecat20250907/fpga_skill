"""Presentation of the original held-out evaluation; never estimates accuracy."""
import math


def summary(report):
    out = {}
    for key in ('valid_rate', 'completed_points', 'expected_points'):
        value = report.get(key)
        if isinstance(value, (int, float)) and math.isfinite(value):
            out[key] = value
    out['filtered'] = {}
    for key in ('mean_frame_error_px', 'p90_frame_error_px', 'grid_8x8_hit_rate', 'grid_8x8_hit_rate_dwell'):
        value = (report.get('filtered') or {}).get(key)
        if isinstance(value, (int, float)) and math.isfinite(value):
            out['filtered'][key] = value
    return out


def scorecard(calib):
    if calib.get('phase') not in ('READY', 'RESULT'):
        return None
    if calib['phase'] == 'READY':
        return {'title': '标定已完成', 'rows': ['已建立当前使用者的个人映射', '独立评测后才能报告准确度'],
                'hint': '比 V 评测 · 竖拇指或确认键使用'}
    report = calib.get('evaluation') or {}
    metrics = report.get('filtered') or {}
    rows = []
    for key, label, percent in (
        ('mean_frame_error_px', '平均偏差', False),
        ('p90_frame_error_px', '各目标 P90 的平均值', False),
        ('grid_8x8_hit_rate', '8×8 单帧命中', True),
        ('grid_8x8_hit_rate_dwell', '8×8 停留命中', True)):
        v = metrics.get(key)
        if isinstance(v, (int, float)) and math.isfinite(v):
            rows.append(label + (f'  {v:.0%}' if percent else f'  {v:.0f} px'))
    if not rows:
        rows.append('没有有效评测结果，请重新标定')
    if 'valid_rate' in report:
        rows.append(f"有效样本 {report['valid_rate']:.0%}")
    if 'completed_points' in report and 'expected_points' in report:
        rows.append(f"有效目标 {report['completed_points']}/{report['expected_points']}")
    return {'title': '个人评测结果', 'rows': rows,
            'hint': '比 V 再测 · 确认键使用 · 返回后重标定'}


def pill_position(width, height, target=None):
    """Choose the corner farthest from the current normalized target."""
    candidates = [(20, 20), (max(0, width-460), 20),
                  (20, max(0, height-152)), (max(0, width-460), max(0, height-152))]
    if target is None:
        return candidates[-1]
    tx, ty = target[0]*width, target[1]*height
    return max(candidates, key=lambda p: (p[0]+220-tx)**2+(p[1]+66-ty)**2)
