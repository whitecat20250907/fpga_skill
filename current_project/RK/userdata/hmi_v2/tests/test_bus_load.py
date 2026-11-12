"""Actual ZeroMQ sockets, 1 kHz for 10 s, consumer deliberately stalls."""
import socket,time,json
from core.hmibus import Publisher,Subscriber
from core.config import ROOT
def test_1000hz_ten_seconds_stalled_subscriber():
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    address=f'tcp://127.0.0.1:{port}'
    pub=Publisher('vision.hands',address);sub=Subscriber(['vision.hands'],addresses={'vision.hands':address})
    try:
        time.sleep(.15);start=time.monotonic();durations=[]
        for seq in range(10000):
            delay=start+seq*.001-time.monotonic()
            if delay>0:time.sleep(delay)
            before=time.monotonic_ns();assert pub.publish(dict(epoch=7,seq=seq,src_ns=before,hands=[]))
            durations.append((time.monotonic_ns()-before)/1e6)
        sent=time.monotonic();deadline=sent+2
        while time.monotonic()<deadline:
            sub.poll(20);latest=sub.latest('vision.hands')
            if latest and latest['seq']==9999:break
        assert sub.latest('vision.hands')['seq']==9999
        durations.sort();report={'transport':'real ZeroMQ TCP on Windows (target IPC not measured)','messages':10000,'requested_hz':1000,'elapsed_s':sent-start,'send_p95_ms':durations[9499],'send_max_ms':durations[-1],'last_received':9999,'consumer_stalled_s':sent-start}
        (ROOT/'docs/evidence/bus_load.json').write_text(json.dumps(report,indent=2))
    finally:sub.close();pub.close()
