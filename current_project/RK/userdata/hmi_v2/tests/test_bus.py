import socket,time
from core.hmibus import Publisher,Subscriber

def address():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return 'tcp://127.0.0.1:'+str(s.getsockname()[1])

def test_latest_slow_subscriber_no_publisher_block():
    addr=address();p=Publisher('vision.gaze',addr);s=Subscriber(['vision.gaze'],addresses={'vision.gaze':addr})
    try:
        time.sleep(.15);start=time.monotonic()
        for seq in range(10000):p.publish(dict(src_ns=time.monotonic_ns(),seq=seq,epoch=1))
        assert time.monotonic()-start<3
        end=time.monotonic()+2
        while time.monotonic()<end:
            s.poll(10)
            if s.latest('vision.gaze') and s.latest('vision.gaze')['seq']==9999:break
        assert s.latest('vision.gaze')['seq']==9999
    finally:s.close();p.close()

def test_independent_metrics_endpoints():
    from core.hmibus import endpoint
    assert endpoint('sys.metrics',producer='gaze')!=endpoint('sys.metrics',producer='hand')
