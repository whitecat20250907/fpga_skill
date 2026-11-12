from queue import Queue
from console.server import publish_commands

class Sink:
    def __init__(self):self.rows=[]
    def publish(self,row):self.rows.append(row)

def test_request_arriving_after_poll_timestamp_is_not_dropped():
    q=Queue();p=Sink();poll_ns=1_000_000_000
    q.put((poll_ns+1_000_000,{'command':'menu'}))
    seq=publish_commands(q,{'src_ns':poll_ns,'epoch':7},p,9,lambda:poll_ns+2_000_000)
    assert seq==10 and p.rows==[dict(src_ns=poll_ns+1_000_000,seq=10,epoch=7,command='menu')]

def test_queue_age_checked_individually_and_no_replay():
    q=Queue();p=Sink();now=2_000_000_000
    for stamp in (now-900_000_000,now-1_000_000,now+2_000_000):q.put((stamp,{'command':'confirm'}))
    seq=publish_commands(q,{'src_ns':now-10_000_000,'epoch':8},p,0,lambda:now)
    assert seq==1 and len(p.rows)==1 and p.rows[0]['src_ns']==now-1_000_000
    assert publish_commands(q,{'src_ns':now,'epoch':8},p,seq,lambda:now)==1
    assert len(p.rows)==1

def test_stale_engine_does_not_accept_command():
    q=Queue();p=Sink();now=2_000_000_000;q.put((now,{'command':'menu'}))
    assert publish_commands(q,{'src_ns':now-351_000_000,'epoch':8},p,0,lambda:now)==0
    assert not p.rows
