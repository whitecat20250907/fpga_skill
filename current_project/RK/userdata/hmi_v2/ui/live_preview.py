"""Read-only HDMI observation. Uses the existing ring and model messages."""
import math
import time
from pathlib import Path
from collections import deque


EYES = ((33, 160, 158, 133, 153, 144), (362, 385, 387, 263, 373, 380))


def face_boxes(message, epoch, now):
    """Normalized display boxes, with sizes measured in model-source pixels."""
    if (str(message.get('epoch')) != str(epoch) or
            not 0 <= now-message.get('src_ns', 0) <= 350_000_000):
        return []
    boxes = []
    for face in message.get('faces', []):
        if not face.get('valid'):
            continue
        w, h = face.get('source_size', [640, 360])
        if not all(isinstance(v, (float, int)) and math.isfinite(v) and v > 0 for v in (w, h)):
            continue
        rect = face.get('face_rect', [])
        if len(rect) == 4 and all(isinstance(v, (float, int)) and math.isfinite(v) for v in rect) and min(rect[2:]) > 0:
            boxes.append(dict(kind='face', rect=[v/d for v, d in zip(rect, [w, h, w, h])], pixels=rect[2:]))
        points = face.get('landmarks', [])
        if len(points) < 468:
            continue
        for index, ids in enumerate(EYES):
            rows = [points[i] for i in ids]
            if any(len(p) < 2 or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in p[:2]) for p in rows):
                continue
            x, y = min(p[0] for p in rows), min(p[1] for p in rows)
            rw, rh = max(p[0] for p in rows)-x, max(p[1] for p in rows)-y
            if rw <= 0 or rh <= 0:
                continue
            # The draw margin is excluded from the reported eye pixel size.
            boxes.append(dict(kind='eye'+str(index), rect=[(x-1)/w, (y-1)/h, (rw+2)/w, (rh+2)/h], pixels=[rw, rh]))
    return boxes


class Rate:
    """Counter deltas over a one-second window, never polling iterations."""
    def __init__(self):
        self.rows = deque()
        self.identity = None

    def update(self, identity, count, stamp):
        if identity != self.identity or self.rows and (count < self.rows[-1][0] or stamp < self.rows[-1][1]):
            self.rows.clear()
            self.identity = identity
        if not self.rows or stamp > self.rows[-1][1]:
            self.rows.append((count, stamp))
        while len(self.rows) > 2 and self.rows[1][1] < stamp-1_000_000_000:
            self.rows.popleft()
        if len(self.rows) < 2 or stamp-self.rows[0][1] < 200_000_000:
            return None
        return (count-self.rows[0][0])*1e9/(stamp-self.rows[0][1])


def position(width, height, panel_width, panel_height, state):
    """Top-left by default; move only to keep the active target unobscured."""
    margin = 12
    candidates = [(margin, margin), (width-panel_width-margin, margin),
                  (margin, height-panel_height-margin), (width-panel_width-margin, height-panel_height-margin)]
    target = state.get('calib', {}).get('target') if state.get('state') == 'CALIBRATING' else None
    rect = state.get('target_session', {}).get('target', {}).get('rect')
    if target is not None and len(target) >= 2:
        tx, ty = target[0]*width, target[1]*height
        protected = (tx-44, ty-44, 88, 88)
    elif rect and len(rect) == 4:
        protected = rect
    else:
        return candidates[0]
    x, y, w, h = protected
    def overlaps(p):
        return p[0] < x+w+16 and p[0]+panel_width > x-16 and p[1] < y+h+16 and p[1]+panel_height > y-16
    return next((p for p in candidates if not overlaps(p)),
                max(candidates, key=lambda p: (p[0]+panel_width/2-x-w/2)**2+(p[1]+panel_height/2-y-h/2)**2))


def compact_status(state):
    phase = state.get('state')
    if state.get('estop'): return '已暂停'
    if phase == 'DEGRADED': return '连接异常'
    if state.get('participants', {}).get('registration'): return '选择使用者'
    if phase == 'CALIBRATING':
        c = state.get('calib', {})
        if c.get('phase') == 'READY': return '标定完成'
        if c.get('phase') == 'RESULT': return '评测完成'
        return ('评测' if c.get('phase') == 'VALIDATE' else '标定')+f" {c.get('point_i', 0)+1}/{c.get('total', 20)}"
    if state.get('stroke_pending'):
        from core.bindings import label
        return '待确认 · '+label(state['stroke_pending']['target'])
    if state.get('shortcut'): return '待确认 · '+state['shortcut'].get('label', '')
    if phase == 'WRITING':
        writing = state.get('writing', {})
        return {'ARMED': '轨迹就绪', 'COUNTDOWN': '准备记录', 'REC': '记录轨迹', 'RESULT': '轨迹完成'}.get(writing.get('state'), '轨迹就绪')
    session = state.get('target_session', {})
    if session.get('phase') in ('SELECTING', 'LOCKED'):
        if session['phase']=='LOCKED' and not session.get('target'):return '位置已保持'
        return ('选目标' if session['phase'] == 'SELECTING' else '已锁定')+' · '+session.get('target', {}).get('label', '')
    if phase == 'MENU': return '菜单'
    return '就绪' if phase not in ('BOOT', None) else '连接中'


def compact_receipt(text):
    """Strip instructions, preserving execution/error meaning, never invent success."""
    text = str(text or '')
    # Engine receipts are persistent state. The HUD applies a local 3s display
    # interval when their actual text changes; no timer mutates engine state.
    prefixes = ('已执行', '应用未执行', '操作未执行', '应用未响应', '已取消', '已撤回',
                '正在撤回', '正在等待', '没有可撤回', '已确认，正在执行')
    if not text.startswith(prefixes): return ''
    return text.split('；', 1)[0].split('（', 1)[0].replace('已确认，正在执行：', '执行中 · ').replace('应用未响应，请重新操作', '应用未响应')


class LivePreview:
    def __init__(self, run):
        self.path = Path(run)/'frames.memfd'
        self.ring = None
        self.frame = None
        self.last_read = 0
        self.retry_ns = 0
        self.source_rate = Rate()
        self.face_rate = Rate()
        self.face_hz = None
        self.source_hz = None
        self.error = '等待图像'
        self.reads = self.replacements = 0
        self.resize = None
        self.resize_backend = 'waiting'

    def close(self):
        if self.ring:
            self.ring.close()
            self.ring = None
        self.frame = None
        if self.resize:
            self.resize.close()
            self.resize = None

    def read(self, now, epoch):
        if now-self.last_read < 50_000_000 or now < self.retry_ns:
            return False
        self.last_read = now
        try:
            if self.ring is None:
                from vision.bootstrap import install_vendor_resolver
                install_vendor_resolver()
                from core.frame_ring import FrameRing
                self.ring = FrameRing(str(self.path))
            frame = self.ring.latest(after_seq=self.frame.serial if self.frame else None)
            self.reads += 1
            if frame is not None:
                if str(frame.meta['fpga_epoch']) != str(epoch):
                    self.frame = None
                    self.error = '等待同步'
                    return True
                self.frame = frame
                # Hardware frame IDs can skip on transport/admission. Count
                # actual publications, not skipped camera frame numbers.
                self.source_hz = self.source_rate.update(epoch, frame.serial, frame.meta['pub_ns'])
                self.error = ''
                return True
        except (OSError, RuntimeError, ValueError):
            self.close()
            self.replacements += 1
            self.error = '图像连接中'
            self.retry_ns = now+500_000_000
        return False

    def valid(self, now, epoch):
        return self.frame is not None and str(self.frame.meta['fpga_epoch']) == str(epoch) and 0 <= now-self.frame.meta['timestamp_ns'] <= 350_000_000

    def metrics(self, message, epoch, now):
        if str(message.get('epoch')) != str(epoch) or not 0 <= now-message.get('src_ns', 0) < 1_500_000_000:
            self.face_hz = None
            return
        count = message.get('inference', {}).get('face_calls')
        if count is not None:
            self.face_hz = self.face_rate.update((epoch, message.get('instance')), count, message['src_ns'])

    def paint(self, pygame, width, image_height, now, epoch, face):
        surface = pygame.Surface((width, image_height))
        surface.fill('#10191f')
        if not self.valid(now, epoch): return surface, []
        # Direct RGB -> XImage. No JPEG/base64 round trip or full 1080P copy.
        if self.resize is None:
            from console.rga_display import DisplayResize
            self.resize = DisplayResize()
        rgb,self.resize_backend = self.resize.rgb_bytes(self.frame.rgb, width, image_height)
        source = pygame.image.frombuffer(rgb, (width, image_height), 'RGB')
        surface.blit(pygame.transform.flip(source, True, False), (0, 0))
        boxes = [dict(box, rect=[1-box['rect'][0]-box['rect'][2], *box['rect'][1:]])
                 for box in face_boxes(face, epoch, now)]
        for box in boxes:
            rect = [round(v*d) for v, d in zip(box['rect'], [width, image_height, width, image_height])]
            color = {'face': '#a1d1ad', 'eye0': '#7bddeb', 'eye1': '#e8c078'}[box['kind']]
            pygame.draw.rect(surface, color, rect, 1 if box['kind'] == 'face' else 2)
        return surface, boxes
