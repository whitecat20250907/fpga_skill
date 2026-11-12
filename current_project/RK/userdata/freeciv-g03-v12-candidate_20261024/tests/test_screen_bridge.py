"""Transport/geometry safety tests, independent of a model or camera."""
import json
from pathlib import Path
import socket
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from screen_bridge import FreecivScreenInput


class GeometryTransport(unittest.TestCase):
    def setUp(self):
        self.server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.server.bind(('127.0.0.1',0));self.server.settimeout(.3)
        self.bridge=FreecivScreenInput(self.server.getsockname()[1])

    def tearDown(self):
        self.bridge.close();self.server.close()

    def establish(self,rect=(30,140,1800,900),extra=None):
        self.bridge.update()
        request,peer=self.server.recvfrom(8192)
        state=dict(version=1,map=list(rect));state.update(extra or {})
        self.server.sendto(b'state '+request.split(b' ')[1]+b' '+json.dumps(state).encode(),peer)
        for _ in range(10):
            state=self.bridge.update()
            if state:return state
            time.sleep(.002)
        self.fail('Geometry reply did not arrive')

    def test_expanded_army_diagnostics_do_not_truncate_geometry(self):
        army=[dict(id=i,tile=i,hp=10,moves=3,type_id=5,role=2) for i in range(160)]
        state=self.establish(extra=dict(army=army))
        self.assertEqual(len(state['army']),160)
        self.assertTrue(self.bridge.action('wake'))

    def test_map_center_excludes_window_and_header(self):
        self.establish()
        self.assertTrue(self.bridge.gaze_screen(930,590,time.monotonic()))
        message,_=self.server.recvfrom(8192)
        self.assertRegex(message.decode(),r'^gaze2 [0-9]+ 0.500000 0.500000$')

    def test_loss_is_sent_once_and_source_duplicate_is_not_replayed(self):
        self.establish();stamp=time.monotonic()
        self.assertTrue(self.bridge.gaze_screen(930,590,stamp));self.server.recvfrom(8192)
        self.assertFalse(self.bridge.gaze_screen(930,590,stamp))
        self.bridge.invalidate_gaze();self.assertEqual(self.server.recvfrom(8192)[0],b'gaze_lost')
        self.bridge.invalidate_gaze();self.server.settimeout(.02)
        with self.assertRaises(socket.timeout):self.server.recvfrom(8192)

    def test_header_outside_map_never_sends_gaze(self):
        self.establish()
        self.assertFalse(self.bridge.gaze_screen(930,100,time.monotonic()))
        self.server.settimeout(.02)
        with self.assertRaises(socket.timeout):self.server.recvfrom(8192)

    def test_stale_model_sample_and_nan_rejected(self):
        self.establish()
        self.assertFalse(self.bridge.gaze_screen(930,590,time.monotonic()-.36))
        self.assertFalse(self.bridge.gaze_screen(float('nan'),590,time.monotonic()))

    def test_geometry_expires_even_if_game_disappears(self):
        self.establish()
        # Advance the public clock rather than relying on host timer rounding.
        future=self.bridge.received_at+.30
        with patch('screen_bridge.time.monotonic',return_value=future):
            self.assertFalse(self.bridge.gaze_screen(930,590,future))
            self.assertFalse(self.bridge.action('confirm'))

    def test_missing_or_invalid_rectangle_cannot_send_actions(self):
        self.assertFalse(self.bridge.action('wake'))
        request,peer=self.server.recvfrom(8192)
        self.server.sendto(b'state '+request.split(b' ')[1]+b' '+
            b'{"version":1,"map":[0,68,0,900]}',peer)
        time.sleep(.01)
        self.assertFalse(self.bridge.action('confirm'))

    def test_unmatched_nonce_cannot_set_geometry(self):
        self.bridge.update();_,peer=self.server.recvfrom(8192)
        self.server.sendto(b'state '+b'0'*32+b' '+
            b'{"version":1,"map":[0,68,1920,1012]}',peer)
        time.sleep(.01)
        self.assertIsNone(self.bridge.update())

    def test_exactly_existing_five_actions(self):
        self.establish()
        self.assertTrue(self.bridge.action('wake'))
        message,_=self.server.recvfrom(8192)
        self.assertRegex(message.decode(),r'^event [0-9]+ wake$')
        with self.assertRaises(ValueError):self.bridge.action('invented_gesture')

    def test_held_existing_action_fires_once_until_release(self):
        self.establish()
        self.assertTrue(self.bridge.held_action('end'))
        for _ in range(20):self.assertFalse(self.bridge.held_action('end'))
        first,_=self.server.recvfrom(8192)
        self.bridge.held_action(None)
        self.assertTrue(self.bridge.held_action('end'))
        second,_=self.server.recvfrom(8192)
        self.assertEqual(int(second.split()[1]),int(first.split()[1])+1)
        self.server.settimeout(.02)
        with self.assertRaises(socket.timeout):self.server.recvfrom(8192)


if __name__=='__main__':unittest.main()
