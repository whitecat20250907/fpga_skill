"""Explicit transient-track registration owned by the single UI/controller.

No camera, inference, geometry association, OS input or transport. The owner
attaches the verified capture/owner session to both producer packets. Producer
UUIDs are intentionally separate; equal numeric face/hand IDs mean nothing.
"""
from copy import deepcopy
from interaction_ui import MAX_AGE_NS, hft2_metadata

VISUAL, TRAJECTORY, GAME = 0, 1, 2


def fresh(packet, now_ns):
    stamp = packet.get('timestamp_ns')
    return type(stamp) is int and 0 <= now_ns - stamp <= MAX_AGE_NS


def ids(records):
    keys = [r.get('track_id') for r in records]
    if any(type(k) is not int or not 0 < k < 0xFFFFFFFF for k in keys) or len(keys) != len(set(keys)):
        raise ValueError('unique transient track IDs required')
    return keys


class ActorController:
    """Explicit incremental registration and independent controls.

    Call observe only with packets from the owner's verified current capture.
    Registration needs >=3 advancing face AND hand observations spanning >=150ms.
    Existing registered faces must remain visible while exactly one new face and
    one/two unbound hands are introduced by the operator. A lost face suspends tracking while preserving registration. Producer/session
    changes require explicit rebinding; hand retirement is explicit producer data.
    """
    def __init__(self, *, stable_frames=3, stable_ns=150_000_000, people_mode='single'):
        if stable_frames < 3 or stable_ns < 150_000_000:
            raise ValueError('registration stability policy')
        self.stable_frames, self.stable_ns = stable_frames, stable_ns
        self.context = None
        self.people = self.hands = None
        self.registrations = {}
        self.registration_generation = 0
        self.display_slot, self.display_generation = 1, 0
        self.mode, self.command_generation = VISUAL, 0
        self.game_slot = self.game_hand = None
        self.candidate = None
        self.invalidations = []
        self.hand_available = False
        if people_mode not in ('single','dual'):raise ValueError('people mode')
        self.people_mode = people_mode

    def set_people_mode(self, mode):
        if mode not in ('single','dual'):raise ValueError('people mode')
        if mode != self.people_mode:
            self.release_game()
            self.registrations.clear()
            self.candidate = None
            self.display_slot = 1
            self.display_generation += 1
            self.command_generation += 1
            self.people_mode = mode
        return dict(accepted=True, people_mode=mode, registration_required=mode=='dual')

    def _automatic_single(self, people, hands, source):
        """Explicit single-person policy, never a biometric identity claim."""
        valid_faces=[p for p in people if p.get('valid') is True]
        if len(valid_faces)!=1 or len(people)!=1:
            for slot in list(self.registrations):self._invalidate(slot,'single_person_not_unique')
            return self._reject('single_person_not_unique')
        face=valid_faces[0]
        selected=[]
        if self.hand_available and len(hands)<=2:
            for side in ('Left','Right'):
                matches=[h for h in hands if h.get('side')==side and h.get('handedness_confidence',0)>=.7]
                if len(matches)==1:selected.append(dict(source_instance=source[1],track_id=matches[0]['track_id'],side=side))
        previous=self.registrations.get(1)
        key=(self.context,source,face['track_id'],tuple((h['track_id'],h['side']) for h in selected))
        old_key=None if previous is None else ((previous['owner_generation'],previous['capture_session']),
            (previous['face_source_instance'],previous['hand_source_instance']),previous['face_track_id'],
            tuple((h['track_id'],h['side']) for h in previous['hands']))
        if key!=old_key:
            self.release_game()
            self.registration_generation+=1
            self.command_generation+=1
        self.registrations={1:dict(slot=1,method='single_person_automatic',owner_generation=self.context[0],
            capture_session=self.context[1],registration_generation=self.registration_generation,
            face_source_instance=source[0],face_track_id=face['track_id'],hand_source_instance=source[1],
            hands=selected,tracking_state='active',tracking_reason=None,requires_confirmation=False)}
        self.candidate=None
        return dict(accepted=True,observed=True,people_mode='single',registration_required=False,
            hand_available=self.hand_available,hand_count=len(selected))

    def _reject(self, reason):
        return dict(accepted=False, association='UNASSIGNED', reason=reason)

    def _invalidate(self, slot, reason):
        if slot in self.registrations:
            if reason in ('operator_unregistered', 'operator_reregistered'):
                del self.registrations[slot]
                self.command_generation += 1
            else:
                r = self.registrations[slot]
                if r.get('tracking_state') != 'lost' or r.get('tracking_reason') != reason:
                    r.update(tracking_state='lost', tracking_reason=reason)
                    self.command_generation += 1
                if reason in ('capture_owner_session_changed','producer_session_changed'):
                    r['requires_confirmation'] = True
            self.invalidations = (self.invalidations + [dict(slot=slot, reason=reason)])[-8:]
        if self.game_slot == slot:
            self.release_game()

    def _expire(self, now_ns):
        if self.people is None or not fresh(self.people, now_ns):
            for slot in list(self.registrations):
                self._invalidate(slot, 'face_source_expired')
            self.candidate = None
            return False
        # A missing hand packet suppresses display/actions; it is not proof that
        # the producer tracker retired a particular ID.
        available = bool(self.hands is not None and self.hands.get('valid') is True and fresh(self.hands, now_ns))
        if not available:
            self._suspend_hand()
        return available

    def _suspend_hand(self):
        """Availability loss is not evidence of a new person/producer identity."""
        self.candidate = None
        if self.hand_available:
            self.command_generation += 1
        self.hand_available = False
        if self.hands is not None:
            self.hands['valid'] = False
        # Fresh recovery cannot reuse an armed latch or implicit game claim.
        # The existing game owner also resets its latch on this policy revision.
        self.release_game()

    def observe(self, people_packet, hand_packet, now_ns):
        """Both packets must carry trusted owner_generation/capture_session.

        Do not fill these from the current owner merely to make an old producer
        packet match: the owner must first verify that producer's capture owner.
        """
        self.candidate = self.candidate if self._expire(now_ns) else None
        try:
            context = tuple(people_packet[k] for k in ('owner_generation', 'capture_session'))
            if (any(not isinstance(v, str) or not v for v in context)
                    or context != tuple(hand_packet.get(k) for k in ('owner_generation', 'capture_session'))):
                raise ValueError('capture_owner_context_mismatch')
            source = people_packet.get('source_instance'), hand_packet.get('source_instance')
            if any(not isinstance(v, str) or not v for v in source):
                raise ValueError('producer_identity_unknown')
            people, hands = people_packet['people'], hand_packet['hands']
            face_ids, hand_ids = ids(people), ids(hands)
            if len(people) > 2 or len(hands) > 4:
                raise ValueError('capacity')
            if not fresh(people_packet, now_ns):
                raise ValueError('stale_or_invalid_face_source')
            retired = hand_packet.get('retired_track_ids', [])
            if not isinstance(retired, list) or any(type(k) is not int or k < 1 for k in retired):
                raise ValueError('retired_hand_IDs')
            if self.context is not None and self.context != context:
                for slot in list(self.registrations):
                    self._invalidate(slot, 'capture_owner_session_changed')
                self.mode = VISUAL
                self.command_generation += 1
                self.candidate = None
            self.context = context
            self.people, self.hands = deepcopy(people_packet), deepcopy(hand_packet)
            for slot, r in list(self.registrations.items()):
                if (r['face_source_instance'], r['hand_source_instance']) != source:
                    self._invalidate(slot, 'producer_session_changed')
                elif r['face_track_id'] not in face_ids:
                    self._invalidate(slot, 'face_track_lost')
                else:
                    current_face = next(p for p in people if p['track_id'] == r['face_track_id'])
                    if not current_face.get('valid'):
                        self._invalidate(slot, 'face_observation_invalid')
                    elif not r.get('requires_confirmation') and r.get('tracking_state') != 'active':
                        r.update(tracking_state='active', tracking_reason=None)
                        self.command_generation += 1
                    if any(h['track_id'] in retired for h in r['hands']):
                        r['hands'] = [h for h in r['hands'] if h['track_id'] not in retired]
                        self.command_generation += 1
                        if self.game_slot == slot and self.game_hand in retired:
                            self.release_game()
            # Identity/session/face-loss checks above must run even when a hand
            # result is invalid (mode cutoff or slow first classifier), so an
            # invalid packet cannot conceal a producer/session replacement.
            if not fresh(hand_packet, now_ns) or hand_packet.get('valid') is not True:
                self._suspend_hand()
                if self.people_mode=='single':return self._automatic_single(people,[],source)
                return dict(accepted=True, observed=True, registration_ready=False,
                    hand_available=False, reason='known_hand_source_temporarily_unavailable',
                    registrations_retained=bool(self.registrations))
            if not self.hand_available:
                self.command_generation += 1
            self.hand_available = True
            if self.people_mode=='single':return self._automatic_single(people,hands,source)
            active = [r for r in self.registrations.values() if r.get('tracking_state','active') == 'active']
            assigned_faces = {r['face_track_id'] for r in active}
            assigned_hands = {h['track_id'] for r in active for h in r['hands']}
            pending_faces = [p for p in people if p['track_id'] not in assigned_faces]
            pending_hands = [h for h in hands if h['track_id'] not in assigned_hands]
            if (len(pending_faces) != 1 or not pending_faces[0].get('valid')
                    or not 1 <= len(pending_hands) <= 2):
                self.candidate = None
                return self._reject('need_exactly_one_unbound_face_and_one_or_two_unbound_hands')
            # The operator explicitly introduces the new person/hands. Existing
            # registered faces are continuously present, never inferred by side.
            key = (context, source, pending_faces[0]['track_id'], tuple(sorted(ids(pending_hands))), tuple(sorted(assigned_faces)))
            stamps = (people_packet['timestamp_ns'], hand_packet['timestamp_ns'])
            if self.candidate is None or self.candidate['key'] != key:
                self.candidate = dict(key=key, first=min(stamps), last=stamps, frames=1)
            elif all(s > p for s, p in zip(stamps, self.candidate['last'])):
                self.candidate['last'] = stamps
                self.candidate['frames'] += 1
            return dict(accepted=True, observed=True, registration_ready=self._stable())
        except (KeyError, ValueError, TypeError) as exc:
            for slot in list(self.registrations):
                self._invalidate(slot, str(exc))
            self.candidate = None
            self.people = self.hands = None
            self.hand_available = False
            return self._reject(str(exc))

    def _stable(self):
        c = self.candidate
        return bool(c and c['frames'] >= self.stable_frames and min(c['last']) - c['first'] >= self.stable_ns)

    def register_visible_actor(self, slot, *, now_ns):
        """Explicit operator call; never called by observe or by page switching."""
        if type(slot) is not int or slot not in (1, 2):
            raise ValueError('actor slot')
        if self.people_mode=='single':
            return dict(accepted=slot==1 and 1 in self.registrations,people_mode='single',
                registration_required=False,reason='single_person_automatic')
        if not self._expire(now_ns) or not self._stable():
            return self._reject('visible_person_not_stable_or_ambiguous')
        if slot in self.registrations and self.registrations[slot].get('tracking_state','active') == 'active':
            return self._reject('unregister_slot_before_replacing_actor')
        face_id, pending_ids = self.candidate['key'][2:4]
        face = next(p for p in self.people['people'] if p['track_id'] == face_id)
        pending_hands = [h for h in self.hands['hands'] if h['track_id'] in pending_ids]
        hand_ids = ids(pending_hands)
        for other, r in self.registrations.items():
            if other != slot and (r['face_track_id'] == face['track_id'] or any(h['track_id'] in hand_ids for h in r['hands'])):
                return self._reject('track_already_registered_to_other_actor')
        sides = [h.get('side') if h.get('handedness_confidence', 0) >= .7 else None for h in pending_hands]
        if any(side not in ('Left', 'Right') for side in sides) or len(set(sides)) != len(sides):
            return self._reject('hand_side_ambiguous')
        self.registration_generation += 1
        r = dict(slot=slot, method='operator_registration', owner_generation=self.context[0],
            tracking_state='active', tracking_reason=None, requires_confirmation=False,
            capture_session=self.context[1], registration_generation=self.registration_generation,
            face_source_instance=self.people['source_instance'], face_track_id=face['track_id'],
            hand_source_instance=self.hands['source_instance'], hands=[dict(source_instance=self.hands['source_instance'],
                track_id=h['track_id'], side=side) for h, side in zip(pending_hands, sides)])
        self._invalidate(slot, 'operator_reregistered')
        self.registrations[slot] = r
        self.candidate = None
        self.command_generation += 1
        return dict(accepted=True, association='operator_registered_transient_tracks', registration=deepcopy(r))

    def unregister_actor(self, slot):
        if type(slot) is not int or slot not in (1, 2):
            raise ValueError('actor slot')
        self._invalidate(slot, 'operator_unregistered')
        self.candidate = None

    def select_page(self, slot):
        if type(slot) is not int or slot not in (1, 2):
            raise ValueError('actor slot')
        if self.people_mode=='single' and slot!=1:
            raise ValueError('single_person_page1_only')
        if self.display_slot != slot:
            self.display_slot = slot
            self.display_generation = (self.display_generation + 1) & 0xFFFFFFFF
        return self.display_slot

    def set_mode(self, mode):
        """Owner-only local policy reset after committing its real ModeGate state.

        This method is not another command transport. Prefer sync_mode(view) in
        the relay callback to consume the authoritative existing ModeGate view.
        command_generation here is the registration/claim policy revision, not
        the external mode epoch carried by the producer acknowledgement.
        """
        if type(mode) is not int or mode not in (VISUAL, TRAJECTORY, GAME):
            raise ValueError('interaction mode')
        if self.mode != mode:
            self.mode = mode
            self.command_generation += 1
            # Switching modes never carries old game ownership implicitly.
            self.release_game()

    def sync_mode(self, mode_view):
        self.set_mode(mode_view.code if mode_view.accepted else VISUAL)

    def claim_game(self, slot, hand_track_id, *, now_ns):
        if not self._expire(now_ns) or slot not in self.registrations or self.registrations[slot].get('tracking_state','active') != 'active':
            return self._reject('actor_not_registered')
        r = self.registrations[slot]
        if self.mode != GAME or hand_track_id not in [h['track_id'] for h in r['hands']]:
            return self._reject('game_mode_and_explicit_registered_hand_required')
        if hand_track_id not in ids(self.hands['hands']):
            return self._reject('claimed_hand_not_currently_visible')
        if self.game_slot is not None and (self.game_slot, self.game_hand) != (slot, hand_track_id):
            return self._reject('release_current_game_owner_first')
        if self.game_slot is None:
            self.game_slot, self.game_hand = slot, hand_track_id
            self.command_generation += 1
        return dict(accepted=True, actor_slot=slot, hand_track_id=hand_track_id)

    def release_game(self):
        if self.game_slot is not None:
            self.game_slot = self.game_hand = None
            self.command_generation += 1

    def assignments(self, now_ns):
        self._expire(now_ns)
        return deepcopy(list(self.registrations.values()))

    def game_binding(self, filtered_gaze, *, now_ns):
        """Read-only eligibility for the existing game policy; never sends input.

        Claim and display do not create personal calibration. The same bound
        face model session/track must supply a fresh calibrated TRACK sample.
        The owner checks this before handing the selected real hand to its sole
        original GestureLatch; it resets that latch on policy_generation change.
        """
        if not self._expire(now_ns) or self.mode != GAME or self.game_slot not in self.registrations:
            return None
        r = self.registrations[self.game_slot]
        if r.get('tracking_state','active') != 'active':
            return None
        hand = next((h for h in self.hands['hands'] if h['track_id'] == self.game_hand), None)
        if (hand is None or not self.hands.get('valid') or not fresh(filtered_gaze, now_ns)
                or filtered_gaze.get('source_instance') != r['face_source_instance']
                or filtered_gaze.get('track_id') != r['face_track_id']
                or filtered_gaze.get('mode') != 'TRACK' or not filtered_gaze.get('valid')
                or not filtered_gaze.get('calibration_valid_for_track') or not filtered_gaze.get('projection_valid')
                or tuple(filtered_gaze.get(k) for k in ('owner_generation','capture_session')) != self.context):
            return None
        return dict(actor_slot=self.game_slot, face_track_id=r['face_track_id'],
            face_source_instance=r['face_source_instance'], hand_source_instance=r['hand_source_instance'],
            hand_track_id=self.game_hand, hand=deepcopy(hand), policy_generation=self.command_generation,
            timestamp_ns=self.hands['timestamp_ns'], owner_generation=self.context[0], capture_session=self.context[1])

    def metadata(self, *, now_ns, acknowledged_mode, selected_hand=None, hand_fresh=False, gaze=None):
        self._expire(now_ns)
        r = self.registrations.get(self.display_slot)
        if r and r.get('tracking_state','active') != 'active':
            r = None
        flags = 0
        current = set()
        if r:
            current = set(ids(self.hands['hands'])) if self.hands and fresh(self.hands, now_ns) and self.hands.get('valid') else set()
            flags = 1 | sum(2 if h['side'] == 'Left' else 4 for h in r['hands'] if h['track_id'] in current)
        if (not r or selected_hand is None or selected_hand.get('track_id') not in current
                or selected_hand.get('track_id') not in [h['track_id'] for h in r['hands']]):
            selected_hand, hand_fresh = None, False
        return hft2_metadata(actor_slot=self.display_slot, display_generation=self.display_generation,
            face_track_id=r['face_track_id'] if r else None, face_source_instance=r['face_source_instance'] if r else None,
            association_flags=flags, selected_hand=selected_hand, hand_fresh=hand_fresh,
            gaze=gaze, now_ns=now_ns, interaction_mode=acknowledged_mode)
