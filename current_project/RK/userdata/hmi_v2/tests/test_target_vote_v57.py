from copy import deepcopy
from core.interaction.target_vote import TargetVote
from core.interaction.engine import Engine
from core.config import load
from tests.test_interaction import healthy,message,catalog

ROWS=[dict(id=k,label=k,action='demo.click',rect=r,confidence=1.) for k,r in [('A',[80,80,40,40]),('B',[480,80,40,40])]]
SIZE=[1920,1080]

def sample(v,i,key,rows=ROWS):
    return v.update([100 if key=='A' else 500,100],rows,SIZE,10**10+i*30_000_000,i)


def test_initial_choice_requires_two_distinct_valid_samples():
    v=TargetVote()
    for i in range(1,2):assert sample(v,i,'A') is None
    assert sample(v,2,'A')['id']=='A'
    assert v.details['share']==1 and v.details['streak']==2


def test_same_gaze_frame_polled_hundred_times_is_one_vote():
    v=TargetVote()
    for _ in range(100):assert sample(v,1,'A') is None
    assert len(v.votes)==1 and v.streak==1


def test_single_jump_does_not_move_then_sustained_gaze_switches():
    v=TargetVote()
    for i in range(1,13):sample(v,i,'A')
    assert sample(v,13,'B')['id']=='A'
    assert sample(v,14,'A')['id']=='A'
    switched=None
    for i in range(15,28):
        out=sample(v,i,'B')
        if out['id']=='B':switched=i;break
        assert v.selected['id']=='A'
    assert switched is not None and v.streak>=2 and v.details['share']>=.55 and v.details['margin']>=.08
    assert len(v.votes)==6


def test_weighted_six_sample_scores_match_decay_and_exclude_old_votes():
    v=TargetVote();keys=['A']*4+['B','A']*6
    for i,key in enumerate(keys,1):sample(v,i,key)
    weights={k:sum(.85**age for age,x in enumerate(reversed(keys[-6:])) if x==k) for k in ('A','B')}
    total=sum(weights.values());assert abs(v.details['share']-max(weights.values())/total)<1e-12
    assert abs(v.details['margin']-abs(weights['A']-weights['B'])/total)<1e-12
    assert len(v.votes)==6


def test_alternating_boundary_never_changes_current_target():
    v=TargetVote()
    for i in range(1,13):sample(v,i,'A')
    for i in range(13,65):assert sample(v,i,'B' if i%2 else 'A')['id']=='A'


def test_invalid_gap_breaks_consecutive_run_but_does_not_cast_vote():
    v=TargetVote()
    sample(v,1,'A')
    v.pause();assert len(v.votes)==1 and v.streak==0
    assert sample(v,2,'A') is None
    assert sample(v,3,'A')['id']=='A'


def test_new_takeover_and_removed_target_cannot_reuse_old_selection():
    v=TargetVote()
    for i in range(1,5):sample(v,i,'A')
    assert sample(v,5,'B',ROWS[1:]) is None
    v.reset();assert sample(v,6,'B') is None and len(v.votes)==1


def test_long_pause_restarts_vote_window_keeps_existing_target_until_new_evidence():
    v=TargetVote()
    for i in range(1,13):sample(v,i,'A')
    assert sample(v,40,'B')['id']=='A'
    assert len(v.votes)==1 and v.streak==1


def test_engine_counts_sources_not_ticks_and_keeps_locked_point_after_gaze():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
    e.system('eye_takeover',t);e.out.clear()
    for i in range(1,5):
        now=t+i*30_000_000;catalog(e,now,ROWS)
        e.feed('vision.gaze',message(now,i,valid=True,filtered_xy=[100,100],screen_size=SIZE,calib={'done':True}),now)
        for j in range(20):e.tick(now+j)
        assert e.target_session['vote']['samples']==i
        assert e.cursor['valid']==(i>=2)
    assert e.cursor['xy']==[100,100]
    e.event('confirm','button',now+50,now+50);assert e.target_session['phase']=='LOCKED'
    frozen=deepcopy(e.cursor)
    for i in range(5,12):
        now=t+i*30_000_000
        e.feed('vision.gaze',message(now,i,valid=True,filtered_xy=[500,100],screen_size=SIZE,calib={'done':True}),now);e.tick(now)
    assert e.cursor==frozen and e.snapshot(now)['budget']['gaze_hz']==0


def test_changed_action_or_moved_target_cannot_inherit_old_votes():
    for changed in [dict(ROWS[0],action='demo.next'),dict(ROWS[0],rect=[80,500,40,40])]:
        v=TargetVote()
        for i in range(1,5):sample(v,i,'A')
        assert sample(v,5,'A',[changed]) is None
        assert len(v.votes)==1 and v.streak==1
