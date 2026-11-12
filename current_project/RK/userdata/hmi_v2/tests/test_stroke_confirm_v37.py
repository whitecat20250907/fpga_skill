from core.config import load
from core.interaction.stroke_confirm import StrokeConfirm
from tests.test_interaction import observation,healthy,message
from tests.test_gesture_actions_v34 import stroke_engine


def gate():
    g=StrokeConfirm(load()['gestures']);t=10**10
    assert g.begin(message(t,label='L'),'demo.zoom_in',dict(track_id=1,side='Right',side_score=.99),(),t)
    return g,t


def step(g,t,name='Closed_Fist',key=2,side='Left'):
    m=observation(t,t,name)
    m['hands'][0].update(track_id=key,side=side,side_score=.99)
    if name is None:m['hands']=[]
    return g.observe(m,m['hands'],t)


def test_short_gap_preserves_release_but_never_supplies_a_pose():
    g,t=gate();assert not step(g,t+1,'Open_Palm')
    assert not step(g,t+100_000_000,None)
    assert not g.pending['other_hand_ready'] and g.pending['progress']==0
    commits=[]
    for i in range(2,11):commits.append(step(g,t+i*100_000_000))
    assert sum(commits)==1


def test_release_does_not_transfer_to_new_track_or_survive_long_gap():
    for new_id,delay in ((3,100_000_000),(2,500_000_000)):
        g,t=gate();step(g,t+1,'Open_Palm')
        for i in range(12):assert not step(g,t+delay+i*100_000_000,key=new_id)


def test_confident_nonfist_releases_but_unknown_does_not():
    for name,expected in [('Victory',True),('Pointing_Up',True),('None',False)]:
        g,t=gate();step(g,t+1,name)
        commits=[step(g,t+i*100_000_000) for i in range(1,10)]
        assert any(commits)==expected


def test_stale_open_palm_cannot_arm_a_later_fist():
    g,t=gate();m=observation(t,1,'Open_Palm');m['hands'][0].update(track_id=2,side='Left',side_score=.99)
    assert not g.observe(m,m['hands'],t+400_000_000)
    for i in range(5,15):assert not step(g,t+i*100_000_000)


def face_proposal(registered=True,dual=False):
    e,t=stroke_engine();e.people.faces=[dict(track_id=50,valid=True,face_rect=[100,100,100,100])]
    if registered:e.people.slots[1]=50
    e.people.last_seen[50]=t
    if dual:
        e.people.mode='dual'
        e.people.faces.append(dict(track_id=51,valid=True,face_rect=[450,100,100,100]))
        e.people.last_seen[51]=t
        e.latest['vision.hands']['hands'][0]['image21']=[[150/640,.5,0]]*21
    e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    assert e.stroke_confirm.pending
    return e,t


def test_brief_face_gap_does_not_cancel_but_new_person_and_long_loss_do():
    e,t=face_proposal(dual=True);e.people.faces=[]
    assert e._stroke_invalid_reason(t+300_000_000) is None
    assert e._stroke_invalid_reason(t+1_100_000_000)=='使用者已离开，请重新画'
    e.people.faces=[dict(track_id=52)]
    assert e._stroke_invalid_reason(t+400_000_000)=='检测到新的使用者，请重新画'


def test_missing_face_tick_preserves_pending_until_loss_budget():
    e,t=face_proposal(dual=True);healthy(e,t+300_000_000);e.tick(t+300_000_000)
    assert e.stroke_confirm.pending and not e.out
    healthy(e,t+1_100_000_000);e.tick(t+1_100_000_000)
    assert not e.stroke_confirm.pending and not e.out


def test_same_hand_fist_and_preheld_other_hand_still_do_not_confirm():
    g,t=gate()
    for i in range(1,11):assert not step(g,t+i*100_000_000)
    step(g,t+1_100_000_000,'Open_Palm')
    for i in range(12,22):assert not step(g,t+i*100_000_000,key=1,side='Right')


def test_single_unregistered_zoom_survives_face_track_churn_and_confirms():
    e,t=face_proposal(registered=False)
    assert not e.stroke_confirm.pending['face_guard']
    e.people.faces=[dict(track_id=51,valid=True,face_rect=[100,100,100,100])]
    assert e._stroke_invalid_reason(t+5_900_000_000) is None
    for i,name in enumerate(['Open_Palm']*2+['Closed_Fist']*9):
        now=t+6_000_000_000+i*100_000_000;healthy(e,now)
        m=observation(now,i+2,name);m['hands'][0].update(track_id=2,side='Left',side_score=.99)
        e.feed('vision.hands',m,now)
    assert len(e.out)==1 and e.out[0]['name']=='demo.zoom_in'
    assert e.out[0]['confirmation']=='opposite_hand'


def test_single_unregistered_still_cancels_on_mode_or_application_change():
    for what in ('context','mode'):
        e,t=face_proposal(registered=False)
        if what=='context':e.context='GAME'
        else:e.people.mode='dual'
        assert e._stroke_invalid_reason(t+1)=='应用或使用者已切换，请重新画'


def test_dual_mode_always_retains_face_guard():
    e,t=stroke_engine();e.people.mode='dual';e.people.slots[1]=50
    e.people.faces=[dict(track_id=50,valid=True,face_rect=[100,100,100,100]),
                    dict(track_id=51,valid=True,face_rect=[450,100,100,100])]
    e.people.last_seen={50:t,51:t}
    e.latest['vision.hands']['hands'][0]['image21']=[[150/640,.5,0]]*21
    e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    assert e.stroke_confirm.pending['face_guard']
    e.people.faces[1]['track_id']=52
    assert e._stroke_invalid_reason(t+2)=='检测到新的使用者，请重新画'


def test_recognized_palm_is_ready_without_a_second_open_gesture():
    for score,count,expected in ((.53,5,True),(.49,5,False),(.53,1,True)):
        g,t=gate()
        for i in range(count):
            now=t+(i+1)*60_000_000;m=observation(now,i+1,'Open_Palm',score)
            m['hands'][0].update(track_id=2,side='Left',side_score=.99)
            assert not g.observe(m,m['hands'],now)
        commits=[]
        for i in range(1,12):commits.append(step(g,now+i*100_000_000))
        assert any(commits)==expected


def test_recorded_left_palm_and_fist_sequence_confirms_once():
    import json
    from pathlib import Path
    data=json.loads((Path(__file__).parent/'fixtures/left_confirm_v38.json').read_text())
    g=StrokeConfirm(load()['gestures'])
    assert g.begin(data['stroke'],'demo.zoom_out',data['source'],(),data['begin_ns'])
    commits=[]
    for sample in data['hands']:
        m=sample['message']
        if g.observe(m,m['hands'],sample['now']):commits.append(m['src_ns'])
    assert len(commits)==1
    assert commits[0]<g.pending['expires_ns']


def test_other_hand_already_open_before_result_needs_no_second_open():
    e,t=stroke_engine()
    e.latest['vision.hands']['hands'].append(dict(track_id=2,side='Left',side_score=.98,gesture='Open_Palm',score=.53,in_bounds=True))
    e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    assert e.stroke_confirm.pending['other_hand_ready']
    for i in range(1,10):
        now=t+i*100_000_000;healthy(e,now)
        m=observation(now,i+2,'Closed_Fist');m['hands'][0].update(track_id=2,side='Left',side_score=.98)
        e.feed('vision.hands',m,now)
    assert len(e.out)==1 and e.out[0]['confirmation']=='opposite_hand'


def test_other_hand_already_fisted_before_result_cannot_execute():
    g,t=gate()
    peers=[dict(track_id=2,side='Left',side_score=.99,gesture='Closed_Fist',score=.95)]
    g.begin(message(t,label='L'),'demo.zoom_in',dict(track_id=1,side='Right',side_score=.99),(),t,peers=peers)
    for i in range(1,12):assert not step(g,t+i*100_000_000)
