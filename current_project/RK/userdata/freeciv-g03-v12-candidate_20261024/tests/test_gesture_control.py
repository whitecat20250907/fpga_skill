"""Meaningful event-safety cases, independent of model availability."""
import unittest
from gesture_control import GestureLatch,action_allowed,send_game_action

class GesturePolicyTest(unittest.TestCase):
    def setUp(self):self.latch=GestureLatch();self.t=1.
    def feed(self,name,seconds,score=.99,hand=True,age=.02):
        found=[]
        for _ in range(round(seconds/.1)):
            self.t+=.1
            x=self.latch.observe(name,score,hand,self.t,self.t+age)
            if x:found.append(x)
        return found
    def release(self):return self.feed(None,.5,1.,False)
    def test_initial_pose_requires_release(self):
        self.assertEqual(self.feed('Thumb_Up',2),[])
    def test_each_mapping_fires_once_then_requires_release(self):
        for name,action in [('Pointing_Up','wake'),('Closed_Fist','confirm'),('Thumb_Down','cancel'),('Victory','next'),('Thumb_Up','end')]:
            self.release();self.assertEqual(self.feed(name,1.5),[action])
            self.assertEqual(self.feed(name,1),[])
            self.assertEqual(self.feed('Open_Palm',1),[])
    def test_jitter_does_not_rearm(self):
        self.release();self.assertEqual(self.feed('Victory',1),['next'])
        self.feed('Victory',1,.4);self.assertEqual(self.feed('Victory',1),[])
    def test_short_hold_and_stale_are_rejected(self):
        self.release();self.assertEqual(self.feed('Thumb_Up',.5),[])
        self.assertEqual(self.feed('Thumb_Up',2,age=.4),[])
    def test_frame_gap_breaks_hold(self):
        self.release();self.feed('Closed_Fist',.4);self.t+=2
        self.assertEqual(self.feed('Closed_Fist',.4),[])
    def test_duplicate_source_frame_cannot_complete_hold(self):
        self.release();self.feed('Victory',.2)
        self.assertIsNone(self.latch.observe('Victory',1.,True,self.t,self.t+.1))
    def test_stale_absence_cannot_arm(self):
        self.feed(None,1,1.,False,age=.5)
        self.assertEqual(self.feed('Thumb_Up',2),[])
    def test_game_state_gates_wake_confirm(self):
        self.assertTrue(action_allowed('wake',{'awake':False}))
        self.assertFalse(action_allowed('wake',{'awake':True}))
        self.assertFalse(action_allowed('confirm',{'awake':False}))
        self.assertTrue(action_allowed('confirm',{'awake':True}))
        self.assertFalse(action_allowed('next',None))
        self.assertFalse(action_allowed('end',{'awake':1}))
    def test_two_widely_spaced_frames_cannot_execute(self):
        self.release();self.feed('Victory',.1);self.t+=.5
        self.assertEqual(self.feed('Victory',.1),[])
    def test_three_Hz_hold_tolerates_one_dropped_preview(self):
        self.release();events=[]
        for gap in (.33,.33,.66,.33):
            self.t+=gap
            action=self.latch.observe('Closed_Fist',.9,True,self.t,self.t+.1)
            if action:events.append(action)
        self.assertEqual(events,['confirm'])
    def test_existing_global_sequence_is_respected(self):
        class Link:
            sequence=10
            def update(self):return dict(awake=False,last_event='10000')
            def action(self,name):self.sequence+=1;return True
        link=Link();self.assertTrue(send_game_action(link,'next'))
        self.assertEqual(link.sequence,10001)

if __name__=='__main__':unittest.main()
