import io,struct,threading
from types import SimpleNamespace
import pytest
from console.preview_stream import frame_chunk,serve
from console.basic_preview import pack_images


def snap(seq=1):return dict(epoch='1',publication_serial=seq,raw_publication=1,raw_image=b'jpeg',model_image=b'model',planes=[])


def test_stream_envelope_preserves_existing_packet_bytes():
    packet=pack_images(snap());chunk=frame_chunk(packet)
    assert struct.unpack_from('<I',chunk)[0]==len(packet)
    assert chunk[4:]==packet


@pytest.mark.parametrize('packet',[b'',b'notHBP1!',b'HBP1'+b'0'*(4*1024*1024)],ids=['empty','magic','oversize'])
def test_invalid_packet_bounded_before_write(packet):
    with pytest.raises(ValueError):frame_chunk(packet)


class Handler:
    def __init__(self):
        self.wfile=io.BytesIO();self.close_connection=False;self.timeouts=[];self.connection=SimpleNamespace(settimeout=self.timeouts.append);self.headers={};self.status=None
    def reply(self,status,value):self.status=status
    def send_response(self,status):self.status=status
    def send_header(self,k,v):self.headers[k]=v
    def end_headers(self):pass


def test_stream_sends_only_new_publication_and_releases_slot(monkeypatch):
    monkeypatch.setattr('console.preview_stream.time.sleep',lambda _:None)
    h=Handler();slots=threading.BoundedSemaphore(1);rows=iter([snap(),snap(),snap(2)])
    count=[0]
    def capture(*args):count[0]+=1;return next(rows)
    serve(h,SimpleNamespace(_dispatch=capture),lambda:({},{}),lambda:count[0]<3,slots)
    raw=h.wfile.getvalue();packets=[]
    while raw:
        size,raw=raw.split(b'\r\n',1);n=int(size,16)
        if not n:assert raw==b'\r\n';break
        packets.append(raw[:n]);raw=raw[n+2:]
    assert len(packets)==2 and h.status==200 and h.headers['Transfer-Encoding']=='chunked'
    assert h.timeouts==[3.,10.] and slots.acquire(blocking=False)


def test_disconnect_releases_slot_and_stops_capture(monkeypatch):
    monkeypatch.setattr('console.preview_stream.time.sleep',lambda _:None)
    h=Handler();h.wfile=SimpleNamespace(write=lambda _:(_ for _ in ()).throw(BrokenPipeError()))
    slots=threading.BoundedSemaphore(1)
    serve(h,SimpleNamespace(_dispatch=lambda *a:snap()),lambda:({},{}),lambda:True,slots)
    assert h.close_connection and slots.acquire(blocking=False)


def test_busy_stream_does_not_start_another_image_worker():
    slots=threading.BoundedSemaphore(1);slots.acquire();h=Handler()
    serve(h,None,None,None,slots)
    assert h.status==429 and not slots.acquire(blocking=False)
