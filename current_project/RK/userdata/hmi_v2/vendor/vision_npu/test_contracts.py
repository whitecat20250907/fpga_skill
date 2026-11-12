import sys,unittest
from types import SimpleNamespace as NS
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gesture8_rk3576_20261021'))
from multi_trajectory import MultiTrajectory
from vision_pipeline import anchors,project,weighted_nms,normalize_object
class Contracts(unittest.TestCase):
    def test_anchor_counts(self):
        self.assertEqual(anchors(128).shape,(896,2));self.assertEqual(anchors(192).shape,(2016,2))
    def test_rotated_projection_pixel_and_z_scaling(self):
        p=project(np.array([[50,50,20],[100,50,0]],np.float32),[320,180,200,100,np.pi/2],100,640,360)
        np.testing.assert_allclose(p[0],[.5,.5,.0625],atol=1e-6)
        np.testing.assert_allclose(p[1],[.5,280/360,0],atol=1e-6)
    def test_nms_keeps_four_distinct_objects(self):
        box=np.array([[i*2,0,i*2+1,1] for i in range(4)],np.float32)
        self.assertEqual(len(weighted_nms(box,np.ones(4),4)),4)
        self.assertEqual(len(weighted_nms(np.repeat(box[:1],4,axis=0),np.ones(4),4)),1)
    def prediction(self,label,step=0,ids=(10,20,30,40)):
        hands=[]
        for i in range(len(ids)):
            p=[NS(x=.2+i*.15,y=.4,z=0.) for _ in range(21)]
            p[8]=NS(x=.2+i*.15+step*.01,y=.4+step*.012,z=0.);hands.append(p)
        return NS(track_ids=list(ids),hand_landmarks=hands,gestures=[[NS(category_name=label,score=.99)] for _ in ids],handedness=[[NS(category_name='Right',score=.99)] for _ in ids])
    def test_four_independent_strokes(self):
        m=MultiTrajectory();seq=0;outputs=[]
        labels=['Open_Palm']+['Closed_Fist']*3+['Pointing_Up']*2+['Pointing_Up']*8+['Closed_Fist']*3
        for label in labels:
            seq+=1;now=10+seq*.05
            outputs+=m.update(self.prediction(label,seq),seq,now,now,640,360)
        self.assertEqual({x[0] for x in outputs},{10,20,30,40});self.assertEqual(len(outputs),4)
        self.assertTrue(all(x[1].shape==(28,28) for x in outputs))
    def test_lost_identity_cancels_instead_of_reassigning(self):
        m=MultiTrajectory();m.update(self.prediction('Open_Palm'),1,10,10,640,360)
        m.update(self.prediction('Closed_Fist',ids=(11,20,30,40)),2,10.1,10.1,640,360)
        self.assertNotIn(10,m.recorders);self.assertFalse(m.recorders[11].released)
    def test_stale_frame_cancels_all(self):
        m=MultiTrajectory();m.update(self.prediction('Open_Palm'),1,10,10,640,360)
        m.update(self.prediction('Closed_Fist'),2,10.1,11,640,360)
        self.assertTrue(all(x.reason=='stale_source' for x in m.recorders.values()))
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):MultiTrajectory().update(self.prediction('Open_Palm',ids=(1,1)),1,1,1,640,360)
if __name__=='__main__':unittest.main()
