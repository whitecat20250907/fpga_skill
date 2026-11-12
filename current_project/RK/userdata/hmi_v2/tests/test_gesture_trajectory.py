import pytest
pytest.importorskip('cv2')
from types import SimpleNamespace as NS
from vision.bootstrap import install_vendor_resolver
from vision.gesture_flow import GestureTrajectory


def result(name,x=.4,track=9):
    points=[NS(x=x,y=.5,z=0.) for _ in range(21)]
    return NS(track_ids=[track],hand_landmarks=[points],
              gestures=[[NS(category_name=name,score=.95)]],
              handedness=[[NS(category_name='Right',score=.95)]])


def test_fist_point_countdown_draw_fist_uses_original_raster_without_menu():
    install_vendor_resolver();flow=GestureTrajectory()
    state=dict(state='ONBOARD',epoch=7,people='single',active_hand_ids=[9])
    sequence=0;now=10.
    def step(name,count,x=.4):
        nonlocal sequence,now
        done=[]
        for _ in range(count):
            sequence+=1;now+=.1
            done+=flow.update(result(name,x),sequence,now,now,640,360,state)
        return done
    assert not step('Closed_Fist',3)
    assert flow.recorders[9].state=='ARMED'
    step('Pointing_Up',2);assert flow.recorders[9].state=='COUNTDOWN'
    step('Pointing_Up',11);assert flow.recorders[9].state=='REC'
    state.update(state='WRITING',layer='WRITE')
    for x in (.4,.43,.46,.49,.52,.55):step('Pointing_Up',1,x)
    done=step('Closed_Fist',3)
    assert len(done)==1 and done[0][0]==9 and done[0][1].shape==(28,28)
    from demo_trajectory import trajectory_to_image
    import numpy as np
    assert np.array_equal(done[0][1],trajectory_to_image(flow.recorders[9].points))
    assert not step('Closed_Fist',3)  # No duplicate classification on a held fist.


def test_static_branch_cannot_later_start_stroke_without_new_fist():
    install_vendor_resolver();flow=GestureTrajectory();state=dict(state='ONBOARD',epoch=7,active_hand_ids=[9])
    for i,name in enumerate(['Closed_Fist']*3+['Victory']+['Pointing_Up']*20):
        now=10+i*.1;assert not flow.update(result(name),i+1,now,now,640,360,state)
    assert flow.recorders[9].state=='IDLE'
    flow.update(result('Closed_Fist'),25,13.,13.,640,360,dict(state,state='MENU'))
    assert not flow.recorders


def test_unselected_hand_and_loss_never_finish_other_person_stroke():
    install_vendor_resolver();flow=GestureTrajectory();state=dict(state='ONBOARD',epoch=7,active_hand_ids=[9])
    for i in range(3):flow.update(result('Closed_Fist'),i+1,10+i*.1,10+i*.1,640,360,state)
    assert flow.recorders[9].state=='ARMED'
    flow.update(result('Pointing_Up',track=10),4,10.3,10.3,640,360,state)
    assert not flow.recorders
