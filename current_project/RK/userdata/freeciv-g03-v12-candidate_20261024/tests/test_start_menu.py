import unittest
from start_menu import MenuModel

TARGETS=[dict(id=i,x=100+i*200,y=300) for i in range(4)]
class StartMenu(unittest.TestCase):
    def test_ordinary_gaze_and_sleep_cannot_start(self):
        m=MenuModel();m.sample(500,300,TARGETS,10);m.event('confirm',10.1);self.assertIsNone(m.result)
    def test_mode_confirm_sleeps_then_explicit_start(self):
        m=MenuModel();m.event('wake',10)
        for t in (10.01,10.05,10.1,10.2):m.sample(300,300,TARGETS,t)
        m.event('confirm',10.21)
        self.assertEqual(m.mode,'hotseat');self.assertFalse(m.awake);self.assertIsNone(m.result)
        m.event('wake',11)
        for t in (11.01,11.05,11.1,11.2):m.sample(500,300,TARGETS,t)
        m.event('confirm',11.21)
        self.assertEqual(m.result,'hotseat')
    def test_stale_and_invalid_coordinates(self):
        m=MenuModel();m.event('wake',10);m.sample(500,300,TARGETS,10.01);m.event('confirm',10.5);self.assertIsNone(m.result)
        m.datagram(b'gaze nan 0.5',TARGETS,1024,600,10.6);self.assertEqual(m.stamp,0)
    def test_bad_events_do_not_poison_sequence(self):
        m=MenuModel()
        for text in (b'event -1 wake',b'event 18446744073709551616 wake',b'event 999 junk',b'event 77 wake extra'):
            m.datagram(text,TARGETS,1024,600)
        self.assertEqual(m.last_event,0)
        m.datagram(b'event 1 wake',TARGETS,1024,600);self.assertTrue(m.awake)
        m.datagram(b'event 1 cancel',TARGETS,1024,600);self.assertTrue(m.awake)
    def test_delayed_source_and_loss_cannot_confirm(self):
        m=MenuModel();m.event('wake',10)
        for stamp in (10.01,10.05,10.1,10.2):
            m.datagram(f'gaze2 {round(stamp*1e6)} .5 .5'.encode(),TARGETS,1000,600,stamp)
        self.assertTrue(m.selection.ready)
        m.datagram(b'gaze_lost',TARGETS,1000,600,10.21);m.event('confirm',10.22)
        self.assertIsNone(m.result)
        m.datagram(b'gaze2 10200000 .5 .5',TARGETS,1000,600,10.6)
        self.assertFalse(m.selection.ready)
if __name__=='__main__':unittest.main()
