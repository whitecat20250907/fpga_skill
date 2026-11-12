import math,unittest
from semantic_selection import Selection
T=[dict(kind=0,id=11,arg=0,x=100.,y=100.),dict(kind=1,id=12,arg=0,x=300.,y=100.)]
def hold(s,x=100.,start=10.,hz=30,duration=.5):
    for i in range(round(hz*duration)+1):
        stamp=start+i/hz;s.sample(x,100.,T,stamp,stamp,True)
    return stamp
class Semantic(unittest.TestCase):
    def test_preview_is_immediate_but_three_distinct_frames_required(self):
        s=Selection();s.sample(100,100,T,10,10)
        self.assertEqual(s.preview(10),0);self.assertFalse(s.confirmable(10))
        s.sample(100,100,T,10.2,10.2)
        self.assertFalse(s.confirmable(10.2))
        s.sample(100,100,T,10.4,10.4)
        self.assertTrue(s.confirmable(10.4))
    def test_preview_moves_while_previous_pick_is_blocked(self):
        s=Selection();stamp=hold(s)
        s.sample(300,100,T,stamp+.03,stamp+.03)
        self.assertEqual(s.preview(stamp+.03),1)
        self.assertEqual(s.pick,0);self.assertFalse(s.confirmable(stamp+.03))
        self.assertEqual(s.preview(stamp+.281),-1)
    def test_preview_preserves_identity_on_reorder(self):
        s=Selection();s.sample(100,100,T,10,10);s.sync(T[::-1])
        self.assertEqual(s.preview(10),1)
    def test_ambiguous_preview_is_not_a_hidden_confirm_target(self):
        s=Selection();s.sample(200,100,T,10,10)
        self.assertEqual(s.preview(10),-1);self.assertFalse(s.ready)
    def test_frame_rates_have_bounded_time_not_frame_count(self):
        times=[]
        for hz in (10,20,30,60):
            s=Selection()
            for i in range(hz):
                stamp=10+i/hz;s.sample(100,100,T,stamp,stamp)
                if s.ready:times.append(i/hz);break
            self.assertTrue(s.confirmable(stamp));self.assertEqual(s.pick,0)
        self.assertTrue(all(.12<=v<=.301 for v in times),times)
    def test_boundary_jitter_has_no_confirmable_target(self):
        s=Selection()
        for i in range(90):
            stamp=10+i/30;s.sample(195 if i%2 else 205,100,T,stamp,stamp)
            self.assertFalse(s.ready)
    def test_spike_blocks_confirmation_without_switching_old_highlight(self):
        s=Selection();stamp=hold(s)
        s.sample(300,100,T,stamp+.03,stamp+.03)
        self.assertEqual(s.pick,0);self.assertFalse(s.confirmable(stamp+.03))
        hold(s,300,stamp+.06);self.assertEqual(s.pick,1);self.assertTrue(s.ready)
    def test_one_far_target_does_not_claim_whole_screen(self):
        s=Selection()
        for i in range(20):s.sample(900,100,T[:1],10+i*.03,10+i*.03)
        self.assertEqual(s.pick,-1);self.assertFalse(s.ready)
    def test_identity_survives_reorder_but_changes_clear_evidence(self):
        s=Selection();hold(s);s.sync(T[::-1]);self.assertEqual(s.pick,1);self.assertTrue(s.ready)
        s.sync([dict(T[0],x=110),T[1]]);self.assertEqual(s.pick,-1);self.assertFalse(s.ready)
        hold(s);s.sync(T[1:]);self.assertFalse(s.ready);self.assertEqual(s.pick,-1)
    def test_replayed_timestamp_cannot_build_confidence(self):
        s=Selection()
        for _ in range(100):s.sample(100,100,T,10,10.1)
        self.assertFalse(s.ready)
    def test_invalid_loss_gap_and_future_clear(self):
        for value in ('lost','gap','future','nan','stale'):
            s=Selection();stamp=hold(s)
            if value=='lost':s.reset()
            elif value=='gap':s.sample(100,100,T,stamp+.3,stamp+.3)
            elif value=='future':s.sample(100,100,T,stamp+1,stamp+.1)
            elif value=='nan':s.sample(math.nan,100,T,stamp+.03,stamp+.03)
            else:s.sample(100,100,T,stamp+.03,stamp+.31)
            self.assertFalse(s.ready,value)
    def test_confirmation_expires_without_new_sample(self):
        s=Selection();stamp=hold(s);self.assertFalse(s.confirmable(stamp+.251))
    def test_filtered_input_bypasses_second_smoother(self):
        s=Selection();hold(s);s.sample(300,100,T,10.53,10.53,True);self.assertEqual(s.x,300)
        s=Selection();hold(s);s.sample(300,100,T,10.53,10.53,False);self.assertLess(s.x,300)
if __name__=='__main__':unittest.main()
