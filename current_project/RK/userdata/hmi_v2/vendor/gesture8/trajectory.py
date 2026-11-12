"""Trajectory-only state machine. Consumes an existing MediaPipe result, no camera/model."""
import math
import cv2
import numpy as np


def trajectory_to_image(points, size=28, line_width=1):
    # Keep the original training raster exactly, including top-left placement.
    canvas = np.zeros((size, size), dtype=np.uint8)
    if len(points) < 2:
        return canvas
    pts = np.array(points, dtype=np.float32)
    low, high = pts.min(axis=0), pts.max(axis=0)
    scale = max(high - low)
    if scale < 1e-3:
        return canvas
    pts = (pts - low) / scale
    pad = line_width + 1
    pts = np.round(pts * (size - 2 * pad) + pad).astype(np.int32)
    for a, b in zip(pts, pts[1:]):
        cv2.line(canvas, tuple(a), tuple(b), 255, line_width, lineType=cv2.LINE_8)
    return canvas


def observations(result):
    hands = []
    for i, landmarks in enumerate(result.hand_landmarks):
        if len(landmarks) != 21:
            continue
        xy = np.asarray([(p.x, p.y) for p in landmarks], dtype=float)
        if not np.isfinite(xy).all() or (xy < 0).any() or (xy > 1).any():
            continue
        categories = result.gestures[i] if i < len(result.gestures) else []
        handed = result.handedness[i] if i < len(result.handedness) else []
        hands.append(dict(tip=xy[8], wrist=xy[0],
                          label=categories[0].category_name if categories else None,
                          score=float(categories[0].score) if categories else 0.,
                          side=handed[0].category_name if handed else None,
                          side_score=float(handed[0].score) if handed else 0.))
    return hands


class TrajectoryRecorder:
    """Fresh source frames only; ambiguity/loss cancels instead of switching hands.

    Input coordinates are unmirrored camera coordinates. Mirror x once to match
    infer.py's webcam flip. Native 640x360 aspect is preserved, never stretched.
    Neutral release is required initially and after a result/cancellation.
    """
    def __init__(self):
        self.state = 'IDLE'
        self.last_stamp = self.last_sequence = None
        self.since = 0.
        self.last_seen = None
        self.wrist = None
        self.side = None
        self.count = 0
        self.points = []
        self.released = False
        self.reason = 'neutral_required'

    def cancel(self, reason, now):
        self.state, self.since = 'IDLE', now
        self.points, self.count, self.wrist, self.side = [], 0, None, None
        self.last_seen, self.released, self.reason = None, False, reason

    def tick(self, now):
        if self.state == 'RESULT' and now - self.since >= 1.2:
            self.cancel('cooldown_complete', now)
        elif self.state == 'ARMED' and now - self.since > 4.:
            self.cancel('arm_timeout', now)
        elif self.state == 'REC' and now - self.since > 10.:
            self.cancel('record_timeout', now)
        elif self.state in ('ARMED', 'REC') and self.last_seen is not None and now-self.last_seen > 1.:
            self.cancel('hand_lost', now)

    def update(self, hands, sequence, source_time, now, width=640, height=360):
        self.tick(now)
        if not math.isfinite(source_time) or not 0 <= now-source_time <= .35:
            self.cancel('stale_source', now)
            return None
        if self.last_stamp is not None and (source_time <= self.last_stamp or sequence == self.last_sequence):
            self.count = 0
            return None
        self.last_stamp, self.last_sequence = source_time, sequence
        if self.state == 'RESULT':
            return None
        if self.state == 'IDLE' and not hands:
            self.count, self.wrist, self.side, self.released = 0, None, None, True
            return None
        # Never infer a persistent hand ID from a MediaPipe list index.
        if self.wrist is None:
            if len(hands) != 1:
                self.count = 0
                if not hands:
                    self.released = True
                return None
            hand = hands[0]
        else:
            candidates = [h for h in hands if
                          (not self.side or h['side'] == self.side) and
                          np.linalg.norm(h['wrist']-self.wrist) <= .25]
            if len(candidates) != 1:
                self.count = 0
                if self.state == 'IDLE' or len(candidates) > 1:
                    self.cancel('ambiguous_hand', now)
                return None
            hand = candidates[0]
        self.last_seen = source_time
        label = hand['label'] if math.isfinite(hand['score']) and hand['score'] >= .5 else None
        if self.state == 'IDLE':
            if label != 'Closed_Fist':
                self.released, self.count = True, 0
                self.wrist, self.side = None, None
                return None
            if not self.released:
                return None
            if self.wrist is None:
                self.wrist = hand['wrist'].copy()
                self.side = hand['side'] if hand['side_score'] >= .7 else None
            self.count += 1
            if self.count >= 3:
                self.state, self.since, self.count = 'ARMED', now, 0
        elif self.state == 'ARMED':
            self.count = self.count+1 if label == 'Pointing_Up' else 0
            if self.count >= 2:
                self.state, self.since, self.count = 'REC', now, 0
                self.points = []
        elif self.state == 'REC':
            self.count = self.count+1 if label == 'Closed_Fist' else 0
            if label != 'Closed_Fist':
                # Mirror, then truncate pixels, matching original infer.py.
                tip = (int((1.-hand['tip'][0])*width), int(hand['tip'][1]*height))
                if not self.points or math.dist(tip, self.points[-1]) > 4:
                    self.points.append(tip)
            if self.count >= 3:
                self.state, self.since, self.count = 'RESULT', now, 0
                raster = trajectory_to_image(self.points)
                if len(self.points) < 5 or np.count_nonzero(raster) < 3:
                    self.reason = 'short_or_empty_trajectory'
                    return None
                self.reason = 'trajectory_complete'
                return raster
        self.wrist = hand['wrist'].copy()
        return None
