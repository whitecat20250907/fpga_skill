from types import SimpleNamespace
import math
import pytest
from ui.live_preview import EYES, Rate, LivePreview, face_boxes, position, compact_status, compact_receipt


def sample():
    points = [[320., 180., 0.] for _ in range(478)]
    for k, ids in enumerate(EYES):
        for i, index in enumerate(ids):
            points[index] = [300+k*32+(i % 3)*4, 170+(i // 3)*3, 0]
    return dict(epoch=7, seq=3, src_ns=10**9, faces=[dict(valid=True, source_size=[640, 360],
        face_rect=[280, 140, 100, 120], landmarks=points)])


def test_small_eyes_measured_in_source_pixels_not_enlarged_preview_pixels():
    boxes = face_boxes(sample(), 7, 10**9)
    assert [b['kind'] for b in boxes] == ['face', 'eye0', 'eye1']
    assert boxes[1]['pixels'] == [8, 3]
    assert boxes[1]['rect'][2:] == [10/640, 5/360]


@pytest.mark.parametrize('epoch,now', [(8, 10**9), (7, 10**9-1), (7, 1_350_000_001)])
def test_stale_or_other_epoch_boxes_are_not_presented_as_current(epoch, now):
    assert not face_boxes(sample(), epoch, now)


def test_bad_eye_does_not_hide_other_valid_eye():
    message = sample()
    message['faces'][0]['landmarks'][33][0] = math.nan
    assert [b['kind'] for b in face_boxes(message, 7, 10**9)] == ['face', 'eye1']


def test_source_rate_counts_source_frames_not_preview_polls():
    rate = Rate()
    assert rate.update('a', 0, 10**9) is None
    assert rate.update('a', 40, 2*10**9) == 40
    for _ in range(20): assert rate.update('a', 40, 2*10**9) == 40
    assert rate.update('b', 0, 3*10**9) is None
    assert rate.update('b', 10, 4*10**9) == 10
    assert rate.update('b', 0, 5*10**9) is None


def test_preview_epoch_and_source_age_gate():
    preview = LivePreview('/not/opened')
    preview.frame = SimpleNamespace(meta=dict(fpga_epoch=7, timestamp_ns=10**9))
    assert preview.valid(10**9, 7)
    assert not preview.valid(10**9, 8)
    assert not preview.valid(1_350_000_001, 7)


def test_active_calibration_and_locked_target_avoidance():
    assert position(1920, 1080, 288, 190, {}) == (12, 12)
    state = {'state':'CALIBRATING', 'calib':{'target':[.08, .07]}}
    assert position(1920, 1080, 288, 190, state)[0] > 1000
    locked = {'target_session':{'target':{'rect':[20, 20, 100, 100]}}}
    assert position(1920, 1080, 288, 190, locked)[0] > 1000


def test_short_status_preserves_failure_and_does_not_invent_success():
    assert compact_status({'state':'IDLE'}) == '就绪'
    assert compact_status({'state':'DEGRADED'}) == '连接异常'
    assert compact_status({'state':'IDLE','target_session':{'phase':'LOCKED','target':{'label':'肾脏'}}}) == '已锁定 · 肾脏'
    assert compact_receipt('已识别 L，等待另一只手确认') == ''
    assert compact_receipt('应用未执行：目标不存在') == '应用未执行：目标不存在'
    assert compact_receipt('已执行：放大') == '已执行：放大'
    assert compact_receipt('已确认，正在执行：放大') == '执行中 · 放大'
    assert compact_receipt('已取消当前操作；没有可撤回的已执行动作') == '已取消当前操作'
