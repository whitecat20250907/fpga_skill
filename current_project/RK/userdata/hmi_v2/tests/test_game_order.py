from adapters.game import submit

class Game:
    def __init__(self):self.last_source=1.;self.gaze_active=True;self.events=[];self.available=True
    def gaze_screen(self,x,y,stamp):
        self.events.append(('gaze',x,y,stamp))
        if not self.available:return False
        self.last_source=stamp;self.gaze_active=True;return True
    def invalidate_gaze(self):self.events.append(('lost',));self.gaze_active=False;return True

def action(stamp=2_000_000_000):
    return {'name':'game.confirm','args':{'cursor':{'xy':[10,20],'screen_origin':[1920,0],'src_ns':stamp}}}

def send(game,name):game.events.append(('event',name));return True

def test_confirm_publishes_final_gaze_before_event_and_sleep():
    game=Game()
    assert submit(game,action(),send)
    game.invalidate_gaze()
    assert game.events==[('gaze',1930,20,2.),('event','confirm'),('lost',)]

def test_confirm_same_source_does_not_replay_gaze():
    game=Game()
    assert submit(game,action(1_000_000_000),send)
    assert game.events==[('event','confirm')]
    game.invalidate_gaze()
    assert not submit(game,action(1_000_000_000),send)

def test_confirm_rejects_unavailable_or_older_gaze():
    game=Game();game.available=False
    assert not submit(game,action(),send)
    assert not submit(game,action(900_000_000),send)
    assert not any(event[0]=='event' for event in game.events)
