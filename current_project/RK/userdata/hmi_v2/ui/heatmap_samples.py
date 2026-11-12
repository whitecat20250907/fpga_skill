"""Display-only gaze samples. The FPGA owns accumulation, decay and color."""
import math
import secrets


class HeatmapSamples:
    def __init__(self, session=None):
        self.context = session or secrets.randbits(32) or 1
        self.identity = None
        self.enabled = False
        self.source = None
        self.token = 0

    def select(self, state, face, gaze, now):
        gaze = gaze or {}
        rows = (face or {}).get('faces', [])
        actor = next((f for f in rows if f.get('primary') and f.get('valid')), None)
        stamp = (face or {}).get('src_ns', 0)
        enabled = bool(actor and state.get('calibrated') and
                       state.get('state') != 'CALIBRATING' and
                       face.get('epoch') == state.get('epoch') and
                       0 < stamp <= now and now-stamp <= 350_000_000)
        if enabled and state.get('people') == 'dual':
            person = state.get('participants', {})
            selected = person.get('slots', {}).get(str(person.get('active', 1)), {})
            enabled = selected.get('track_id') == actor['track_id']
        identity = (state.get('epoch'), actor.get('track_id') if actor else None,
                    gaze.get('source_instance'), gaze.get('calibration_request'))
        if identity != self.identity or enabled != self.enabled:
            self.context = (self.context+1) & 0xffffffff or 1
            self.identity = identity
            self.enabled = enabled
        word = (1 << 31) if enabled else 0
        source = (gaze.get('epoch'), gaze.get('source_instance'), gaze.get('seq'), gaze.get('src_ns', 0))
        stamp = source[3]
        fresh = isinstance(stamp, int) and 0 < stamp <= now and now-stamp <= 250_000_000
        if not (enabled and state.get('state') == 'POINTING' and gaze.get('valid') and
                gaze.get('epoch') == state.get('epoch') and gaze.get('track_id') == actor['track_id'] and fresh):
            return self.context, word
        if self.source and source[:2] == self.source[:2] and (source[2] == self.source[2] or stamp <= self.source[3]):
            return self.context, word
        try:
            x, y = gaze['filtered_xy'];w, h = gaze['screen_size']
            if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
                return self.context, word
            x = round(min(1., max(0., x/w))*127)
            y = round(min(1., max(0., y/h))*103)
        except (KeyError, TypeError, ValueError, OverflowError):
            return self.context, word
        self.source = source
        self.token = (self.token+1) & 0xffff
        return self.context, word | (1 << 30) | (self.token << 14) | (y << 7) | x
