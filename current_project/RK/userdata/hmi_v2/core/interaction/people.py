"""Explicit session bindings. Spatial track IDs are never biometric identities."""
from core.clock import fresh


class People:
    def __init__(self):
        self.mode = 'single'
        self.active = 1
        self.slots = {1: None, 2: None}
        self.calibrated = {1: False, 2: False}
        self.faces = []
        self.last_seen = {}
        self.pending = None
        self.hand_owners = {}

    def observe(self, message, now):
        rows = message.get('faces', []) if fresh(message.get('src_ns'), 350, now) else []
        self.faces = [f for f in rows if f.get('valid') and type(f.get('track_id')) is int]
        for face in self.faces:
            self.last_seen[face['track_id']] = message['src_ns']
        lost = []
        for slot, track in self.slots.items():
            if self.mode=='dual' and track is not None and now-self.last_seen.get(track, 0) > 1_000_000_000:
                self.calibrated[slot] = False
                lost.append(slot)
        self.last_seen = {track: stamp for track, stamp in self.last_seen.items()
                          if now-stamp <= 2_000_000_000 or track in self.slots.values()}
        return lost

    def request(self, slot):
        other = self.slots[3-slot]
        choices = sorted((f for f in self.faces if f['track_id'] != other),
                         key=lambda f: f.get('face_rect', [0])[0])
        self.pending = {'slot': slot, 'choices': [f['track_id'] for f in choices], 'index': 0}
        return bool(choices)

    def next_candidate(self):
        if self.pending and self.pending['choices']:
            p = self.pending
            p['index'] = (p['index']+1) % len(p['choices'])

    def confirm(self):
        p = self.pending
        if not p or not p['choices']:
            return None
        track = p['choices'][p['index']]
        if track not in {f['track_id'] for f in self.faces}:
            return None
        slot = p['slot']
        if self.slots[slot] != track:
            self.calibrated[slot] = False
        self.slots[slot] = track
        self.active = slot
        self.pending = None
        return track

    def hands_for_active(self, hands):
        if self.mode == 'single':
            return hands if len(hands) <= 2 else []
        target = self.slots[self.active]
        if target is None or len(self.faces) != 2:
            return []
        centers = [(f['track_id'], (f['face_rect'][0]+f['face_rect'][2]/2)/640)
                   for f in self.faces]
        result = []
        present = {h.get('track_id') for h in hands}
        self.hand_owners = {track: owner for track, owner in self.hand_owners.items() if track in present}
        for hand in hands:
            points = hand.get('image21', [])
            if len(points) != 21:
                continue
            distances = sorted((abs(points[0][0]-x), track) for track, x in centers)
            # Lock a hand track to its first unambiguous side. Crossing the
            # midline disarms it until it disappears and returns as a new track.
            # This is spatial association, not biometric identity recognition.
            track = hand.get('track_id')
            clear = distances[1][0]-distances[0][0] >= .12
            if track not in self.hand_owners and clear:
                self.hand_owners[track] = distances[0][1]
            elif track in self.hand_owners and (not clear or self.hand_owners[track] != distances[0][1]):
                self.hand_owners[track] = None
            if clear and distances[0][1] == target and self.hand_owners.get(track) == target:
                result.append(hand)
        return result if len(result) <= 2 else []

    def snapshot(self):
        return {'mode': self.mode, 'active': self.active,
                'slots': {str(k): {'track_id': v, 'calibrated': self.calibrated[k]}
                          for k, v in self.slots.items()}, 'registration': self.pending, 'faces': [{'track_id': f['track_id'], 'face_rect': f['face_rect']} for f in self.faces]}
