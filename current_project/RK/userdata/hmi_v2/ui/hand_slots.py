"""Use anatomical model labels, never the order in a detection array."""
def hand_slots(hands):
    slots={}
    for hand in hands:
        group={'Left':0,'Right':1}.get(hand.get('side'))
        if group is None:continue
        if group in slots:
            # Ambiguous same-side claims must not be relabelled as the other hand.
            slots[group]=None
        else:slots[group]=hand
    return [(group,hand) for group,hand in sorted(slots.items()) if hand is not None]


class DisplayHandSlots:
    """Keep a live track in its anatomical viewport despite label jitter.

    Only display placement is retained. Geometry is never replayed, and this
    association never qualifies a gesture, action or person identity.
    """
    def __init__(self):self.context=None;self.assignments={}

    def select(self,hands,now,context):
        if context!=self.context:self.assignments={};self.context=context
        self.assignments={k:v for k,v in self.assignments.items() if 0<=now-v[1]<=350_000_000}
        result=[];used=set()
        # Existing tracks retain priority over a new duplicate label.
        for hand in sorted(hands,key=lambda h:h['track_id'] not in self.assignments):
            key=hand['track_id'];prior=self.assignments.get(key)
            group=prior[0] if prior else {'Left':0,'Right':1}.get(hand.get('side'))
            if group is None or group in used:continue
            if not prior and hand.get('side_score',1.)<.7:continue
            self.assignments[key]=(group,now);used.add(group);result.append((group,hand))
        return sorted(result,key=lambda x:x[0])
