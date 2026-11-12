"""Inference demand is independent of UI visibility and retained calibration."""


def demand(state, *, estop=False, registration=False, calibration=False,
           calibration_phase=None, dual=False, target_phase=None, head_display_hz=15):
    if estop or state in ('BOOT', 'DEGRADED'):
        return {'gaze_hz': 0, 'face_hz': 0, 'reason': 'paused'}
    if state == 'CALIBRATING' and calibration_phase not in ('READY', 'RESULT', 'FAILED'):
        return {'gaze_hz': 30, 'face_hz': 30, 'reason': 'calibration'}
    if state == 'POINTING' and target_phase not in ('LOCKED', 'CONFIRMING'):
        return {'gaze_hz': 32, 'face_hz': 32, 'reason': 'target_selection'}
    if registration or calibration:
        return {'gaze_hz': 0, 'face_hz': 15, 'reason': 'registration'}
    if dual:
        # Hands are assigned from live face geometry, never stale rectangles.
        return {'gaze_hz': 0, 'face_hz': 10, 'reason': 'dual_hand_ownership'}
    return {'gaze_hz': 0, 'face_hz': head_display_hz,
            'reason': 'head_display' if head_display_hz else 'hands_only'}
