"""Real Linux cross-process locks, immutable snapshots, and stale rejection."""
import fcntl,json,mmap,multiprocessing as mp,os,struct,sys,time
from pathlib import Path
sys.path.insert(0,'/userdata/freeciv-rk3576-gaze-demo')
from shared_model_frame import SharedModelFrame,HEADER,PAYLOAD
from model_frame_reader import ExistingModelFrame
def producer(pipe):
    with_store=SharedModelFrame()
    pipe.send((os.getpid(),with_store.fd))
    try:
        while True:
            command=pipe.recv()
            if command=='quit':break
            if command=='lock':fcntl.lockf(with_store.fd,fcntl.LOCK_EX);pipe.send(True);continue
            if command=='unlock':fcntl.lockf(with_store.fd,fcntl.LOCK_UN);pipe.send(True);continue
            if command=='invalidate':struct.pack_into('<I',with_store.map,24,0);pipe.send(True);continue
            now=time.monotonic_ns();meta=dict(timestamp_ns=now-1_000_000,dequeue_ns=now,sequence=command)
            pipe.send(with_store.publish(bytes([command%256])*PAYLOAD,meta))
    finally:with_store.close();pipe.close()
def main():
    ctx=mp.get_context('spawn');a,b=ctx.Pipe();p=ctx.Process(target=producer,args=(b,));p.start();pid,fd=a.recv()
    r=ExistingModelFrame.__new__(ExistingModelFrame);r.fd=os.open(f'/proc/{pid}/fd/{fd}',os.O_RDONLY);r.map=mmap.mmap(r.fd,0,access=mmap.ACCESS_READ)
    r.last_serial=r.last_stamp=0;r.stats=dict(busy=0,stale=0,duplicate=0,invalid=0,accepted=0)
    # Full /proc owner attachment is covered by the separate actual-main live trial.
    r.check_owners=lambda:None
    def send(value):a.send(value);return a.recv()
    try:
        assert r.read() is None
        assert send(1);rgb,meta=r.read();assert not rgb.flags.writeable and (rgb==1).all()
        assert r.read() is None
        assert send(2);second,_=r.read();assert (second==2).all() and (rgb==1).all()
        assert send('lock');t=time.monotonic();assert r.read() is None;assert time.monotonic()-t<.1;send('unlock')
        fcntl.lockf(r.fd,fcntl.LOCK_SH);assert send(3) is False;fcntl.lockf(r.fd,fcntl.LOCK_UN)
        assert send(4);time.sleep(.27);assert r.read() is None
        assert send('invalidate');assert r.read() is None
        assert send(5);assert (r.read()[0]==5).all()
        report=dict(status='PASS',stats=r.stats,immutable=True,lock_nonblocking=True,partial_stale_duplicate_rejected=True)
        Path(__file__).with_name('shared_frame_test.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
    finally:
        a.send('quit');p.join(5);r.close();a.close();assert p.exitcode==0
if __name__=='__main__':main()
