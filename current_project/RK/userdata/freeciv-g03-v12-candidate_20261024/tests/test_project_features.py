import copy,json,math,types,unittest
from project_features import FeatureState,face_features,face_points_isotropic
from project_twin import project,render

def packet(stamp=1_000_000_000):
    return dict(version=1,kind='hand',timestamp_ns=stamp,sequence=1,hands=[dict(side='Right',confidence=.9,
        gesture='Victory',world=[[i*.001,-i*.002,i*.0005] for i in range(21)],image=[[.5,.5,0.]]*21)])
class Features(unittest.TestCase):
    def test_four_hand_capacity_and_fifth_rejection(self):
        p=packet();p['hands']=[copy.deepcopy(p['hands'][0]) for _ in range(4)]
        self.assertTrue(FeatureState().accept(json.dumps(p),1_000_000_001))
        p['hands'].append(copy.deepcopy(p['hands'][0]))
        self.assertFalse(FeatureState().accept(json.dumps(p),1_000_000_001))
    def test_dense_eye_groups_coordinates_and_degenerate_rejection(self):
        f=types.SimpleNamespace(status=True,can_gaze_estimation=False,landmarks_valid=True,img_w=640,img_h=360,
            face_landmarks=[[160+math.cos(i)*20,100+math.sin(i)*10,i%5] for i in range(478)],
            left_eye_valid=True,right_eye_valid=False,left_iris_valid=True,right_iris_valid=True,
            left_eye_openness=20,right_eye_openness=0,capture_sequence=91)
        p=face_features(f,1_000_000_000)
        self.assertTrue(p['valid']);self.assertEqual(p['capture_sequence'],91)
        self.assertTrue(p['groups']['left_iris']);self.assertFalse(p['groups']['right_iris'])
        self.assertAlmostEqual(face_points_isotropic(p)[0][1],100/640,places=5)
        s=FeatureState();self.assertTrue(s.accept(json.dumps(p),1_000_000_001))
        p['eye_left_ear']=float('nan');self.assertFalse(FeatureState().accept(json.dumps(p),1_000_000_001))
        f.face_landmarks=[[0,0,0]]*478;self.assertFalse(face_features(f,1)['valid'])
    def test_source_identity_capture_replay_and_replacement(self):
        s=FeatureState();p=packet();p.update(source_instance='a'*32,packet_sequence=1,capture_sequence=7,boot_id=s.boot_id)
        self.assertTrue(s.accept(json.dumps(p),1_000_000_001))
        p.update(timestamp_ns=1_000_000_010,packet_sequence=2)
        self.assertFalse(s.accept(json.dumps(p),1_000_000_011))
        p['capture_sequence']=8;self.assertTrue(s.accept(json.dumps(p),1_000_000_011))
        q=dict(p,source_instance='b'*32,packet_sequence=1,timestamp_ns=1_400_000_000)
        self.assertTrue(s.accept(json.dumps(q),1_400_000_001))
        p.update(timestamp_ns=1_800_000_000,packet_sequence=3,capture_sequence=9)
        self.assertFalse(s.accept(json.dumps(p),1_800_000_001))
    def test_source_age_and_repeat(self):
        s=FeatureState();p=packet();self.assertTrue(s.accept(json.dumps(p),p['timestamp_ns']+10))
        self.assertFalse(s.accept(json.dumps(p),p['timestamp_ns']+20))
        self.assertIsNotNone(s.fresh('hand',p['timestamp_ns']+350_000_000))
        self.assertIsNone(s.fresh('hand',p['timestamp_ns']+350_000_001))
    def test_nan_shape_future(self):
        p=packet();s=FeatureState();p['hands'][0]['world'][2][0]=math.nan
        self.assertFalse(s.accept(json.dumps(p),1_000_000_001))
        p=packet();p['hands'][0]['world'].pop();self.assertFalse(s.accept(json.dumps(p),1_000_000_001))
        self.assertFalse(s.accept(json.dumps(packet()),999_999_999))
    def test_lost_hand_is_not_previous_pose(self):
        s=FeatureState();p=packet();s.accept(json.dumps(p),1_000_000_001)
        p['timestamp_ns']+=10;p['hands']=[];self.assertTrue(s.accept(json.dumps(p),1_000_000_020))
        self.assertEqual(s.fresh('hand',1_000_000_030)['hands'],[])
    def test_real_z_affects_projection(self):
        a=project([[.1,.1,0]],(0,0),100);b=project([[.1,.1,.1]],(0,0),100)
        self.assertNotEqual(a[0][:2],b[0][:2])
    def test_face_invalid_clear(self):
        class Face:status=False
        p=face_features(Face(),1_000_000_000);s=FeatureState()
        self.assertTrue(s.accept(json.dumps(p),1_000_000_001));self.assertFalse(s.fresh('face',1_000_000_002)['valid'])
    def test_render_lost_and_fixture(self):
        s=FeatureState();p=packet();p['fixture']=True;s.accept(json.dumps(p),1_000_000_001)
        a=render(s,1_000_000_002);b=render(s,2_000_000_000)
        self.assertEqual(a.size,(1024,600));self.assertNotEqual(a.tobytes(),b.tobytes())
if __name__=='__main__':unittest.main()
