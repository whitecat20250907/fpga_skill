import ast
import unittest
from pathlib import Path
import cv2
import numpy as np
from trajectory import trajectory_to_image, TrajectoryRecorder

class Tests(unittest.TestCase):
    def setUp(self):
        self.rec = TrajectoryRecorder(); self.now = 100.; self.sequence = 0

    def feed(self, label, tip=(.5,.5), side='Left', wrist=(.5,.7), duplicate=False):
        if not duplicate:
            self.now += .15; self.sequence += 1
        hands = [] if label is None else [dict(label=label,score=.9,tip=np.array(tip),
                    wrist=np.array(wrist),side=side,side_score=.9)]
        return self.rec.update(hands,self.sequence,self.now,self.now+.01)

    def arm(self):
        self.feed(None)
        for _ in range(3):self.feed('Closed_Fist')
        self.assertEqual(self.rec.state,'ARMED')
        for _ in range(2):self.feed('Pointing_Up')
        self.assertEqual(self.rec.state,'REC')

    def test_exact_original_raster(self):
        root = Path(__file__).parent
        tree = ast.parse((root/'original/infer.py').read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='trajectory_to_image')
        scope = dict(np=np,cv2=cv2,IMG_SIZE=28,LINE_WIDTH=1)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'original_raster','exec'),scope)
        rng = np.random.default_rng(63)
        for n in [0,1,2,5,20,200]:
            for _ in range(20):
                points=rng.uniform(-1000,1000,(n,2)).tolist()
                np.testing.assert_array_equal(trajectory_to_image(points),scope['trajectory_to_image'](points))

    def test_neutral_and_duplicate_do_not_arm(self):
        for _ in range(10):self.feed('Closed_Fist')
        self.assertEqual(self.rec.state,'IDLE')
        self.feed(None);self.feed('Closed_Fist')
        for _ in range(10):self.feed('Closed_Fist',duplicate=True)
        self.assertEqual(self.rec.state,'IDLE')

    def test_one_classification_per_stroke_and_mirror(self):
        self.arm()
        for i in range(8):self.feed('Pointing_Up',tip=(.2+i*.04,.3+i*.02))
        self.assertEqual(self.rec.points[0],(512,108))
        self.assertIsNone(self.feed('Closed_Fist'));self.assertIsNone(self.feed('Closed_Fist'))
        self.assertEqual(self.feed('Closed_Fist').shape,(28,28))
        for _ in range(15):self.assertIsNone(self.feed('Closed_Fist'))
        self.assertEqual(self.rec.state,'IDLE')

    def test_other_hand_cannot_finish(self):
        self.arm()
        for i in range(6):self.feed('Pointing_Up',tip=(.2+i*.04,.3))
        for _ in range(4):self.assertIsNone(self.feed('Closed_Fist',side='Right'))
        self.assertEqual(self.rec.state,'REC')
        self.rec.tick(self.now+1.1)
        self.assertEqual(self.rec.state,'IDLE')

    def test_gap_breaks_end_confirmation(self):
        self.arm()
        for i in range(6):self.feed('Pointing_Up',tip=(.2+i*.04,.3))
        self.feed('Closed_Fist');self.feed('Closed_Fist');self.feed(None)
        self.assertIsNone(self.feed('Closed_Fist'))
        self.assertEqual(self.rec.state,'REC')

    def test_stale_and_future_cancel(self):
        for age in [.351,-.01]:
            self.setUp();self.arm()
            self.rec.update([],999,self.now-age,self.now)
            self.assertEqual(self.rec.state,'IDLE')
            self.assertEqual(self.rec.reason,'stale_source')

    def test_timeout_without_any_input(self):
        self.arm();self.rec.tick(self.now+11)
        self.assertEqual(self.rec.state,'IDLE')

    def test_short_stroke_never_classifies(self):
        self.arm();self.feed('Pointing_Up')
        for _ in range(3):self.assertIsNone(self.feed('Closed_Fist'))
        self.assertEqual(self.rec.reason,'short_or_empty_trajectory')

if __name__=='__main__':unittest.main(verbosity=2)
