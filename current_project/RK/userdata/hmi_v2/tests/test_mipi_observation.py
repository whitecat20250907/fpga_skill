from ui.mipi_composer import compose,registers
from hft2_wire import decode

STAMP=10**10

def sample(**changes):
    state=dict(epoch=7,state='ONBOARD',people='single',calibrated=False,
               cursor=dict(valid=True,src_ns=STAMP,xy=[10,20],screen_size=[1920,1080]))
    state.update(changes)
    face=dict(epoch=7,seq=11,src_ns=STAMP,faces=[dict(track_id=7,primary=True,
              valid=True,landmarks=[[0,0,0],[1,0,0],[0,1,0]],face_rect=[100,50,80,100])])
    hands=dict(epoch=7,src_ns=STAMP,hands=[dict(track_id=1,side='Left',world21=[[i%4,i//4,i%3] for i in range(21)])])
    return state,face,hands

def scene(state,face,hands):
    return decode(compose(state,face,hands,STAMP,1)[0])

def test_uncalibrated_single_person_shows_observation_without_gaze_projection():
    state,face,hands=sample()
    result=scene(state,face,hands)
    assert result['scene'].valid==5  # Hand and head, no gaze point.
    assert result['metadata'].association_flags==3
    assert not result['metadata'].ui_status & (7<<13)
    assert scene(dict(state,calibrated=True,state='IDLE'),face,hands)['scene'].valid==13

def test_observation_rejects_stale_sources_and_wrong_hardware_epoch():
    state,face,hands=sample()
    assert scene(state,dict(face,src_ns=STAMP-351_000_000),hands)['scene'].valid==1
    assert scene(state,dict(face,epoch=8),hands)['scene'].valid==1
    assert scene(state,face,dict(hands,epoch=8))['scene'].valid==4
    assert scene(state,face,dict(hands,src_ns=STAMP-351_000_000))['scene'].valid==4

def test_dual_requires_selected_registered_face_and_engine_assigned_hands():
    state,face,hands=sample(people='dual',participants={'active':1,'slots':{'1':{'track_id':None},'2':{'track_id':8}}})
    assert scene(state,face,hands)['scene'].valid==0
    state['participants']['slots']['1']['track_id']=7
    state['active_hand_ids']=[]
    assert scene(state,face,hands)['scene'].valid==4
    state['active_hand_ids']=[1]
    assert scene(state,face,hands)['scene'].valid==5
    state['participants']['active']=2
    assert scene(state,face,hands)['scene'].valid==0


def test_projection_ray_hits_the_actual_screen_inset_and_retains_source_age():
    state,face,hands=sample(calibrated=True,state='POINTING')
    state['cursor'].update(xy=[1920,1080],src_ns=STAMP-100_000_000)
    rendered=scene(state,face,hands)['scene']
    vertices=[v for v in rendered.vertices if v[0]==3]
    assert vertices[0][1:3]==(390*16,106*16)
    assert vertices[1][1:3]==(484*16,134*16)
    assert rendered.face_timestamp_ns==STAMP-100_000_000
    assert rendered.ages[3]>=100
    assert len([e for e in rendered.edges if rendered.vertices[e[0]][0]==3])==3


def test_retained_target_is_csr_display_not_fresh_gaze():
    state,face,hands=sample(calibrated=True,state='IDLE',target_session={'phase':'LOCKED'})
    state['cursor'].update(xy=[960,540],src_ns=1,locked=True)
    assert not scene(state,face,hands)['scene'].valid & 8
    value=registers(state,3)[str(0xc8c)]
    assert value & (1<<21)
    assert value & 1023 == 904
    assert (value>>10)&1023 == 216
    assert registers(dict(state,cursor={}),4)[str(0xc8c)]==0
