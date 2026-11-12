"""Display-only history of actual recorder points; never emits an action."""
from copy import deepcopy


class TraceDisplay:
    def __init__(self):
        self.key = None
        self.cached = None
        self.blocked_before = 0

    def select(self, state, hands, active_hands, now):
        participants = state.get('participants', {})
        actor = participants.get('active', 1)
        key = (state.get('epoch'), state.get('people', 'single'), actor,
               state.get('context'), state.get('gesture_generation', 0),
               participants.get('slots', {}).get(str(actor), {}).get('track_id')
               if state.get('people') == 'dual' else None)
        if key != self.key:
            if self.key is not None:
                self.blocked_before = now
            self.key, self.cached = key, None
        stamp = (hands or {}).get('src_ns', 0)
        allowed = {h['track_id'] for h in active_hands if h.get('side') == 'Right'}
        if (state.get('state') in ('MENU', 'BOOT', 'STANDBY', 'DEGRADED', 'CALIBRATING')
                or state.get('estop') or not hands or not 0 < stamp <= now
                or now - stamp > 350_000_000 or hands.get('epoch') != key[0]
                or hands.get('gesture_generation', 0) != key[4] or not allowed):
            self.cached = None
            self.blocked_before = max(self.blocked_before, now)
            return None
        records = [(int(k), r) for k, r in hands.get('recorder', {}).items()
                   if int(k) in allowed]
        eligible = [(k, r) for k, r in records
                    if r.get('state') in ('REC', 'RESULT') and r.get('points')]
        if len(eligible) > 1:
            self.cached = None
            self.blocked_before = now
            return None
        if any(r.get('state') in ('ARMED', 'COUNTDOWN') for _, r in records):
            self.cached = None
            self.blocked_before = max(self.blocked_before, stamp)
            return None
        stroke = state.get('stroke') or {}
        if eligible:
            track, record = eligible[0]
            if record['state'] == 'REC':
                if stamp < self.blocked_before:
                    return None
                self.cached = dict(track_id=track, points=deepcopy(record['points'][:48]),
                                   src_ns=stamp, phase='REC', result={})
                return deepcopy(self.cached) if state.get('layer') == 'WRITE' else None
            # RESULT snapshots carry a new hand-frame stamp every update.
            # Freeze the points' source on the first observation instead.
            if (self.cached is None or self.cached['phase'] != 'RESULT' or self.cached['track_id'] != track
                    or self.cached['result'] and self.cached['result'].get('src_ns') != stroke.get('src_ns')):
                self.cached = dict(track_id=track, points=deepcopy(record['points'][:48]),
                                   src_ns=stamp, phase='RESULT', result={})
        cached = self.cached
        event_stamp = stroke.get('src_ns', 0)
        if (not cached or cached['track_id'] not in allowed
                or stroke.get('track_id') != cached['track_id']
                or stroke.get('epoch') != key[0]
                or stroke.get('gesture_generation', 0) != key[4]
                or stroke.get('source_side') != 'Right'
                or stroke.get('ending_gesture') != 'Closed_Fist'
                or not self.blocked_before < event_stamp <= now
                or now - event_stamp > 1_200_000_000):
            return None
        cached['src_ns'] = min(cached['src_ns'], event_stamp)
        if now - cached['src_ns'] > 1_200_000_000:
            return None
        cached['phase'], cached['result'] = 'RESULT', deepcopy(stroke)
        return deepcopy(cached)
