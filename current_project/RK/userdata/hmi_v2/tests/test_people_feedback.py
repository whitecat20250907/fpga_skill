from core.config import load
from core.interaction.engine import Engine
from core.interaction.people import People
from ui.feedback import feedback
from tests.test_interaction import healthy, message


def faces(t, ids=(11, 22)):
    return message(t, faces=[dict(track_id=k,valid=True,primary=i==0,
                                  face_rect=[100+320*i,100,120,100],can_gaze=True)
                            for i,k in enumerate(ids)])


def test_binding_requires_confirmation_and_does_not_follow_replacement():
    p=People();t=10**10;p.mode='dual';p.observe(faces(t),t)
    assert p.request(2) and p.slots[2] is None
    p.next_candidate();assert p.confirm()==22
    p.calibrated[2]=True
    p.observe(faces(t+2_000_000_000,(11,33)),t+2_000_000_000)
    assert p.slots[2]==22 and not p.calibrated[2]


def test_vanished_candidate_cannot_be_registered():
    p=People();t=10**10;p.observe(faces(t),t);p.request(1)
    p.observe(faces(t+1,(22,)),t+1)
    assert p.confirm() is None and p.slots[1] is None


def test_four_hands_routed_only_to_selected_actor_midline_rejected():
    p=People();t=10**10;p.mode='dual';p.slots={1:11,2:22};p.observe(faces(t),t)
    hands=[dict(track_id=i,image21=[[x,.6,0]]*21) for i,x in enumerate([.15,.3,.7,.85])]
    assert [h['track_id'] for h in p.hands_for_active(hands)]==[0,1]
    p.active=2
    assert [h['track_id'] for h in p.hands_for_active(hands)]==[2,3]
    assert not p.hands_for_active([dict(track_id=9,image21=[[.5,.6,0]]*21)])


def test_engine_dual_registration_and_independent_calibrations():
    e=Engine(load());t=10**10;healthy(e,t);e.feed('vision.face',faces(t),t)
    e.system('dual',t);e.system('person1',t);e.event('confirm','button',t,t)
    assert e.people.slots[1]==11 and e.commands[-1]['track_id']==11
    e.people.calibrated[1]=True;e.calibrated=True
    e.system('person2',t+1);e.event('confirm','button',t+1,t+1)
    assert e.people.slots[2]==22 and not e.calibrated and e.people.calibrated[1]
    e.feed('vision.gaze',message(t+2,phase='READY',track_id=11,calib={'done':True}),t+2)
    assert not e.calibrated


def test_hdmi_gives_countdown_recording_and_frozen_confirmation_feedback():
    s={'state':'WRITING','writing':{'state':'COUNTDOWN','remaining_s':.4}}
    assert '0.4' in feedback(s)['hint']
    s['writing']['state']='REC';assert '记录' in feedback(s)['title']
    assert '等待目标' in feedback({'state':'POINTING','cursor':{'valid':False}})['hint']

def test_stale_ready_cannot_complete_new_calibration():
    from tests.test_interaction import face
    e=Engine(load());t=10**10;healthy(e,t);e.people.slots[1]=11
    for i in range(7):
        face(e,t+i*100_000_000,i+1);e.tick(t+i*100_000_000)
    t+=600_000_000
    e.system('calibrate',t)
    assert e.state=='CALIBRATING' and e.calibration_request>0
    for seq,request in [(1,e.calibration_request-1),(2,None)]:
        e.feed('vision.gaze',message(t+seq,seq=seq,phase='READY',track_id=11,
               calib={'done':True},calibration_request=request),t+seq)
        assert not e.calibrated
    e.feed('vision.gaze',message(t+3,seq=3,phase='READY',track_id=11,
           calib={'done':True},calibration_request=e.calibration_request),t+3)
    assert e.calibrated

def test_face_publication_stopping_invalidates_calibration_even_without_new_faces():
    e=Engine(load());t=10**10;healthy(e,t);e.feed('vision.face',faces(t,(11,)),t)
    e.people.slots[1]=11;e.people.calibrated[1]=True;e.calibrated=True;e._state('IDLE',t)
    e.people.mode='dual';e.tick(t)
    for offset in (200_000_000,400_000_000,800_000_000,1_100_000_000):
        healthy(e,t+offset);e.tick(t+offset)
    assert not e.calibrated and not e.people.calibrated[1]
    assert any(c['command']=='invalidate_calibration' for c in e.commands)

def test_crossed_hand_cannot_become_the_other_person_by_position():
    p=People();t=10**10;p.mode='dual';p.slots={1:11,2:22};p.observe(faces(t),t)
    hand=lambda x:dict(track_id=9,image21=[[x,.6,0]]*21)
    assert p.hands_for_active([hand(.25)])
    p.active=2
    assert not p.hands_for_active([hand(.75)])
    assert not p.hands_for_active([hand(.75)])

def test_service_fault_invalidates_both_profiles_in_engine():
    e=Engine(load());t=10**10;healthy(e,t);e.people.calibrated={1:True,2:True}
    e.feed('sys.metrics',message(t+1,producer='hand',ok=False),t+1);e.tick(t+1)
    assert e.people.calibrated=={1:False,2:False}
