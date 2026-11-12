"""Bounded UI snapshots from the existing inference owner.

No camera, network, file watcher, hand model, or person-association heuristic.
The optional session consumes ONE existing hand prediction; its only added
inference is the already migrated GestureNet when a real stroke completes.
"""
from __future__ import annotations

import math
import time

CLASSES = ('0', 'L', 'L_rev', 'L_up', 'L_rev_up', 'M', 'W', 'Z')
MAX_HANDS = 4
MAX_POINTS = 48
MAX_AGE_NS = 350_000_000
STATES = ('IDLE', 'ARMED', 'COUNTDOWN', 'REC', 'RESULT')
# Existing FPGA code 1 is preparation; exact countdown is exported to HTML.
STATE_CODES = dict(IDLE=0, ARMED=1, COUNTDOWN=1, REC=2, RESULT=3)
STATIC_CODES = {None: 0, 'None': 0, 'Closed_Fist': 1, 'Pointing_Up': 2,
                'Open_Palm': 3, 'Victory': 4, 'Thumb_Up': 5, 'Thumb_Down': 6}


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(name)
    return value


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name)
    return float(value)


def _score(value):
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('confidence')
    return value


def _fresh(stamp, now):
    return type(stamp) is int and type(now) is int and 0 <= now - stamp <= MAX_AGE_NS


def bounded_points(points, width, height, limit=MAX_POINTS):
    """Select real vertices uniformly; preserve endpoints, never alter training."""
    if not 2 <= limit <= MAX_POINTS:
        raise ValueError('UI point limit')
    n = len(points)
    indices = range(n) if n <= limit else (i * (n - 1) // (limit - 1) for i in range(limit))
    selected = []
    for index in indices:
        point = points[index]
        if len(point) != 2:
            raise ValueError('trajectory shape')
        x, y = map(float, point)
        # Existing recorder int((1-x)*width) can legitimately equal width.
        if not (math.isfinite(x) and math.isfinite(y) and 0 <= x <= width and 0 <= y <= height):
            raise ValueError('trajectory coordinates')
        selected.append([int(x), int(y)])
    return selected


def hand_keys(prediction):
    keys = list(prediction.track_ids)
    if (len(keys) > MAX_HANDS or len(keys) != len(prediction.hand_landmarks)
            or any(type(key) is not int or key < 1 for key in keys) or len(set(keys)) != len(keys)):
        raise ValueError('unique live hand track IDs required')
    return keys


def _classification(event, key, sequence):
    if event.get('track_id') != key or event['label'] not in CLASSES:
        raise ValueError('classification track/label')
    confidence = _score(event['confidence'])
    probabilities = [_score(p) for p in event['probabilities']]
    if len(probabilities) != 8 or abs(sum(probabilities) - 1.) > 1e-4:
        raise ValueError('eight class probabilities')
    index = CLASSES.index(event['label'])
    if abs(probabilities[index] - confidence) > 1e-5 or index != max(range(8), key=probabilities.__getitem__):
        raise ValueError('classification probabilities disagree')
    if type(event['accepted']) is not bool or event['accepted'] != (confidence >= .60):
        raise ValueError('classifier acceptance threshold')
    return dict(label=event['label'], class_index=index, confidence=confidence,
                accepted=event['accepted'], event_sequence=sequence)


class TrajectorySnapshot:
    """Read-only view of owned MultiTrajectory; no calls into its state machine."""
    def __init__(self, source_instance):
        if not isinstance(source_instance, str) or not source_instance:
            raise ValueError('source instance')
        self.source_instance = source_instance
        self.last_stamp = self.last_sequence = None
        self.results = {}

    def observe(self, prediction, trajectories, events, meta, now_ns, width=640, height=360):
        _integer(width, 'width', 1); _integer(height, 'height', 1)
        stamp, sequence = meta['timestamp_ns'], meta['sequence']
        _integer(sequence, 'sequence')
        packet = dict(version=1, kind='interaction_ui', source_instance=self.source_instance,
            timestamp_ns=stamp, capture_sequence=sequence, valid=False, reason='stale_source',
            coordinates='mirrored_camera_pixels', source_size=[width, height], hands=[],
            track_ids_are_person_identity=False, person_assignment='unassigned')
        if not _fresh(stamp, now_ns):
            self.results.clear()
            return packet
        if self.last_stamp is not None and (stamp <= self.last_stamp or sequence == self.last_sequence):
            packet['reason'] = 'duplicate_or_old_source'
            return packet
        keys = hand_keys(prediction)
        self.last_stamp, self.last_sequence = stamp, sequence
        self.results = {k: v for k, v in self.results.items() if k in keys}
        for event in events:
            key = event['track_id']
            if key not in keys or key not in trajectories.recorders or trajectories.recorders[key].state != 'RESULT':
                raise ValueError('classification is not this live completed stroke')
            self.results[key] = _classification(event, key, sequence)
        for index, key in enumerate(keys):
            rec = trajectories.recorders.get(key)
            if rec is None or rec.state not in STATES:
                raise ValueError('record after original MultiTrajectory.update')
            if rec.state != 'RESULT':
                self.results.pop(key, None)
            category = prediction.gestures[index][0] if prediction.gestures[index] else None
            static_name = category.category_name if category else None
            static_confidence = _score(category.score) if category else 0.
            tip = prediction.hand_landmarks[index][8]
            tx, ty = float(tip.x), float(tip.y)
            if not (math.isfinite(tx) and math.isfinite(ty) and 0 <= tx <= 1 and 0 <= ty <= 1):
                # Cropped hands can legitimately predict a point outside the
                # image. The recorder already cancels this observation. Omit
                # its UI/action sample without dropping other valid hands or
                # terminating the shared inference process.
                self.results.pop(key, None)
                continue
            packet['hands'].append(dict(track_id=key, person_slot=None,
                static_gesture=static_name, static_confidence=static_confidence,
                static_label_code=STATIC_CODES.get(static_name, 15),
                state=rec.state, state_code=STATE_CODES[rec.state], reason=rec.reason, released=bool(rec.released),
                # Original recorder's transition time, before classifier work;
                # later hand frames must never restart the 1.2s RESULT lifetime.
                result_started_ns=int(rec.since * 1e9) if rec.state == 'RESULT' else None,
                countdown_remaining_ms=max(0, int((rec.since+1)*1000-now_ns/1e6)) if rec.state=='COUNTDOWN' else 0,
                fingertip=[int((1. - tx) * width), int(ty * height)],
                points=bounded_points(rec.points, width, height), source_point_count=len(rec.points),
                classification=self.results.get(key)))
        packet.update(valid=True, reason='fresh_existing_prediction')
        return packet


class ExistingTrajectorySession:
    """Add original stroke processing to an already-running hand consumer.

    Caller constructs the existing MultiTrajectory and original Classifier once
    under its ExitStack. Call update exactly once per already computed prediction.
    Do not also call an independent run_hands process or second trajectory owner.
    """
    def __init__(self, trajectories, classifier, source_instance):
        self.trajectories, self.classifier = trajectories, classifier
        self.snapshot = TrajectorySnapshot(source_instance)
        self.last_stamp = self.last_sequence = None
        self.classifier_calls = 0

    def update(self, prediction, meta, now_ns, width=640, height=360):
        started = time.perf_counter_ns()
        stamp, sequence = meta['timestamp_ns'], meta['sequence']
        fresh_at_entry = _fresh(stamp, now_ns)
        if self.last_stamp is not None and (stamp <= self.last_stamp or sequence == self.last_sequence):
            return self.snapshot.observe(prediction, self.trajectories, [], meta, now_ns, width, height)
        hand_keys(prediction)
        # This is the original state machine/raster, not a parallel reimplementation.
        finished = self.trajectories.update(prediction, sequence, stamp / 1e9,
                                            now_ns / 1e9, width, height)
        self.last_stamp, self.last_sequence = stamp, sequence
        events = []
        for key, raster in finished:
            event = dict(self.classifier.predict(raster), track_id=key)
            self.classifier_calls += 1
            events.append(event)
        # NPU classification time counts against the same source's freshness.
        completed_ns = now_ns + (time.perf_counter_ns() - started) if fresh_at_entry else now_ns
        return self.snapshot.observe(prediction, self.trajectories, events, meta, completed_ns, width, height)


def attach_to_hand_features(packet, prediction, snapshot):
    """Extend the same existing hand packet; keep the original v1 kind/geometry.

    The existing relay ignores this extra data. A new relay must explicitly read
    interaction_ui; sending the nested interaction as a new v1 kind is invalid.
    """
    keys = hand_keys(prediction)
    if (packet.get('kind') != 'hand' or packet.get('version') != 1
            or packet.get('timestamp_ns') != snapshot['timestamp_ns']
            or packet.get('capture_sequence') != snapshot['capture_sequence']
            or len(packet['hands']) != len(keys)):
        raise ValueError('feature/trajectory source mismatch')
    return dict(packet, hands=[dict(hand, track_id=key, person_slot=None)
                               for hand, key in zip(packet['hands'], keys)],
                valid=bool(snapshot['valid']), interaction_ui=snapshot,
                interaction_mode_ack=snapshot.get('interaction_mode_ack'),
                retired_track_ids=snapshot.get('retired_track_ids', []))


def hft2_metadata(*, actor_slot, display_generation, face_track_id=None,
                  association_flags=0, selected_hand=None, hand_fresh=False,
                  gaze=None, now_ns=None, interaction_mode=0,
                  face_source_instance=None):
    """Exact 112-byte HFT2 semantic extension, not a wire encoder.

    Caller selects ONE sticky hand track for the <=48-vertex trajectory viewport.
    Association flags come only from the trusted explicit registration owner.
    The new relay owns CRC/source epoch, TTL and atomic geometry/metadata publish.
    """
    if type(actor_slot) is not int or actor_slot not in (1,2):raise ValueError('actor slot')
    if type(interaction_mode) is not int or interaction_mode not in (0,1,2):raise ValueError('interaction mode')
    if type(display_generation) is not int or not 0<=display_generation<2**32:raise ValueError('display generation')
    if type(association_flags) is not int or not 0<=association_flags<8:raise ValueError('association flags')
    if association_flags&6 and not association_flags&1:raise ValueError('hand association without registered face')
    if face_track_id is None:
        face_track_id=0xFFFFFFFF
        if association_flags:raise ValueError('unknown face cannot be assigned')
    elif type(face_track_id) is not int or not 0<face_track_id<0xFFFFFFFF:raise ValueError('face track ID')
    draw,static,class_id,confidence,accepted,saved=15,15,15,0,False,0
    if hand_fresh and selected_hand is not None:
        state=selected_hand['state'];classification=selected_hand.get('classification')
        if state not in STATES:raise ValueError('draw state')
        draw=STATE_CODES[state]
        if state=='IDLE' and not selected_hand.get('released'):draw=5
        if state=='RESULT' and (classification is None or not classification['accepted']):draw=4
        static=STATIC_CODES.get(selected_hand.get('static_gesture'),15)
        saved=len(selected_hand['points'])
        if saved>48:raise ValueError('HFT2 trajectory vertex budget')
        if classification is not None:
            class_id=classification['class_index']
            if type(class_id) is not int or not 0<=class_id<=7:raise ValueError('class ID')
            score=_score(classification['confidence'])
            confidence=int(score*255.+.5)
            if type(classification['accepted']) is not bool or classification['accepted']!=(score>=.60):raise ValueError('class acceptance')
            accepted=classification['accepted']
            if state!='RESULT':raise ValueError('result outside RESULT state')
    gaze=gaze or {}
    same_face=bool(association_flags&1 and face_source_instance is not None
        and gaze.get('source_instance')==face_source_instance
        and gaze.get('track_id')==face_track_id and _fresh(gaze.get('timestamp_ns'),now_ns))
    calibrated=bool(same_face and gaze.get('calibration_valid_for_track'))
    # HFT2 wire/native/RTL require TRACK => personally calibrated. This UI
    # eligibility flag does not modify the original application's TRACK phase.
    tracking=bool(same_face and calibrated and gaze.get('mode')=='TRACK')
    projection=bool(same_face and calibrated and tracking and gaze.get('valid') and gaze.get('projection_valid'))
    status=draw|(static<<4)|(class_id<<8)|(int(accepted)<<12)|(int(calibrated)<<13)|(int(tracking)<<14)|(int(projection)<<15)|(interaction_mode<<16)
    return dict(actor_slot=actor_slot,face_track_id=face_track_id,status=status,
                display_generation=display_generation,confidence=confidence,
                actual_saved_points=saved,association_flags=association_flags,reserved=0)


def gaze_screen_view(people_packet, *, selected_track_id, now_ns, mode,
                     calibrated_sample=None, calibration_track_id=None, screen_size=None):
    """Only an explicitly matched, calibrated TRACK sample yields a screen ray.

    Raw MGaze values are never interpreted as pixels, angles or a physical ray.
    Even a calibrated 2-D cursor gives only a schematic eye-to-screen line.
    """
    result = dict(valid=False, reason='no_fresh_person', mode='schematic',
                  track_id=selected_track_id, screen_point=None, ray_is_physical_3d=False)
    if not _fresh(people_packet.get('timestamp_ns'), now_ns):
        return result
    people = people_packet.get('people', [])
    if len(people) > 2:
        raise ValueError('at most two face tracks')
    matches = [p for p in people if p.get('track_id') == selected_track_id]
    if len(matches) != 1 or not matches[0].get('valid'):
        return result
    result.update(reason='calibration_required', raw_model_output=matches[0].get('raw'))
    if mode != 'TRACK' or calibration_track_id != selected_track_id or calibrated_sample is None:
        return result
    if (calibrated_sample.get('timestamp_ns') != people_packet['timestamp_ns']
            or calibrated_sample.get('track_id') != selected_track_id
            or not calibrated_sample.get('valid')):
        result['reason'] = 'calibrated_sample_identity_mismatch'
        return result
    if screen_size is None or len(screen_size) != 2 or any(type(v) is not int or v <= 0 for v in screen_size):
        raise ValueError('explicit calibrated screen size')
    xy = calibrated_sample.get('filtered')
    if xy is None or len(xy) != 2:
        return result
    x, y = (_finite(v, 'screen point') for v in xy)
    width, height = screen_size
    if not (0 <= x < width and 0 <= y < height):
        result['reason'] = 'outside_calibrated_screen'
        return result
    result.update(valid=True, reason='fresh_calibrated_primary', mode='calibrated_2d_schematic_ray',
                  screen_point=[x, y], screen_size=[width, height])
    return result


def person_pages(people_packet, hand_packet, *, assignments, now_ns):
    """Pages require explicit registration; equal face/hand IDs never associate.

    assignments is a trusted owner registry populated by deliberate registration,
    never accepted from the inference packet itself. It binds separate sources.
    A missing/lost track is invalid immediately and is not replaced by list order.
    """
    pages = [dict(slot=i, face=None, hands=[], association='unassigned') for i in (1, 2)]
    people = people_packet.get('people', []) if _fresh(people_packet.get('timestamp_ns'), now_ns) else []
    hands = hand_packet.get('hands', []) if hand_packet.get('valid') and _fresh(hand_packet.get('timestamp_ns'), now_ns) else []
    if len(people) > 2 or len(hands) > 4:
        raise ValueError('two people/four hands capacity')
    used_faces, used_hands, used_slots = set(), set(), set()
    for registration in assignments:
        if registration.get('method') not in ('operator_registration','single_person_automatic'):
            raise ValueError('explicit registration required')
        slot = registration['slot']
        if type(slot) is not int or slot not in (1, 2):
            raise ValueError('page slot')
        if slot in used_slots:
            raise ValueError('page assigned twice')
        used_slots.add(slot)
        page = pages[slot - 1]
        face_key = (registration['face_source_instance'], registration['face_track_id'])
        if page['face'] is not None or face_key in used_faces:
            raise ValueError('duplicate person registration')
        if people_packet.get('source_instance') != face_key[0]:
            continue
        face = next((p for p in people if p.get('track_id') == face_key[1] and p.get('valid')), None)
        if face is None:
            continue
        page.update(face=dict(face), association='operator_registered_transient_tracks')
        used_faces.add(face_key)
        registered_hands = registration.get('hands', [])
        if len(registered_hands) > 2:
            raise ValueError('at most two hands per registered person')
        for hand_key in registered_hands:
            key = (hand_key['source_instance'], hand_key['track_id'])
            if key in used_hands:
                raise ValueError('hand assigned twice')
            if key[0] != hand_packet.get('source_instance'):
                continue
            hand = next((h for h in hands if h['track_id'] == key[1]), None)
            if hand is not None:
                page['hands'].append(dict(hand, person_slot=slot));used_hands.add(key)
    unassigned = [dict(h) for h in hands if (hand_packet.get('source_instance'), h['track_id']) not in used_hands]
    return dict(pages=pages, unassigned_hands=unassigned, person_identity_verified=False)
