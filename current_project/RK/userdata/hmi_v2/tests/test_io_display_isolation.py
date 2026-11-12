import struct
from core.io_service import submit_scene


def test_refused_scene_is_not_retried_and_next_scene_can_succeed():
    calls=[]
    def native(path,payload):
        calls.append(payload)
        return struct.pack('<i',-1 if payload==b'old' else 0)
    assert submit_scene('sock',b'old',native)==-1
    assert submit_scene('sock',b'new',native)==0
    assert calls==[b'old',b'new']


def test_delayed_or_broken_display_reply_is_a_drop_not_capture_shutdown():
    def timeout(*_):raise TimeoutError('display delayed')
    assert submit_scene('sock',b'scene',timeout)==-1002
    assert submit_scene('sock',b'scene',lambda *_:b'')==-1001
