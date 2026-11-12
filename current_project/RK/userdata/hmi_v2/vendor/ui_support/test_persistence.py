import sys,types,unittest
sys.modules['interaction_ui']=types.SimpleNamespace(MAX_AGE_NS=500_000_000,hft2_metadata=lambda **k:k)
from actor_controller import ActorController

class Persistence(unittest.TestCase):
    def setUp(self):
        self.c=ActorController();self.now=1_000_000_000
        for _ in range(3):self.observe()
        self.assertTrue(self.c.register_visible_actor(1,now_ns=self.now)['accepted'])
    def observe(self,face=True,source='face',track=1):
        self.now+=100_000_000
        common=dict(owner_generation='owner',capture_session='capture',timestamp_ns=self.now,valid=True)
        p=dict(common,source_instance=source,people=[dict(track_id=track,valid=True)] if face else [])
        h=dict(common,source_instance='hand',hands=[dict(track_id=2,side='Left',handedness_confidence=.99)])
        self.c.observe(p,h,self.now)
    def test_missed_face_preserves_slot_and_same_track_recovers(self):
        self.observe(face=False)
        self.assertEqual(self.c.registrations[1]['tracking_state'],'lost')
        self.observe()
        self.assertEqual(self.c.registrations[1]['tracking_state'],'active')
    def test_timeout_preserves_slot_and_disarms_game(self):
        self.c.game_slot=1;self.c.game_hand=2
        self.c.assignments(self.now+2_000_000_000)
        self.assertIn(1,self.c.registrations);self.assertIsNone(self.c.game_slot)
        self.assertIsNone(self.c.metadata(now_ns=self.now+2_000_000_000,acknowledged_mode=0)['face_track_id'])
    def test_new_track_does_not_take_identity(self):
        self.observe(track=9)
        self.assertEqual(self.c.registrations[1]['face_track_id'],1)
        self.assertEqual(self.c.registrations[1]['tracking_state'],'lost')
    def test_new_producer_needs_explicit_confirmation(self):
        for _ in range(3):self.observe(source='new')
        self.assertEqual(self.c.registrations[1]['tracking_state'],'lost')
        self.assertTrue(self.c.register_visible_actor(1,now_ns=self.now)['accepted'])
        self.assertEqual(self.c.registrations[1]['face_source_instance'],'new')
    def test_only_explicit_unregister_removes_slot(self):
        self.c.unregister_actor(1);self.assertEqual(self.c.registrations,{})

if __name__=='__main__':unittest.main()
