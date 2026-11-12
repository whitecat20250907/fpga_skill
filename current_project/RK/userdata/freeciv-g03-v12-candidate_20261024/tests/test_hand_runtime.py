import unittest
from hand_runtime import SampleClock,create_recognizer

class HandScheduling(unittest.TestCase):
    def test_uncapped_still_retries_busy_without_repeating_frames(self):
        s=SampleClock(0);s.accepted(1);self.assertEqual(s.delay(1),0)
        s.busy(1);self.assertAlmostEqual(s.delay(1),.005)
        s.accepted(1.005);self.assertEqual(s.delay(1.005),0)
        for fps in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):SampleClock(fps)
    def test_busy_read_does_not_consume_sampling_period(self):
        s=SampleClock(6);s.busy(1)
        self.assertAlmostEqual(s.delay(1),.005)
        s.accepted(1.005)
        self.assertAlmostEqual(s.delay(1.005),1/6)
    def test_long_inference_never_builds_catchup_backlog(self):
        s=SampleClock(10);s.accepted(1)
        self.assertEqual(s.delay(2),0)
        s.accepted(2);self.assertAlmostEqual(s.delay(2),.1)
    def test_invalid_configuration_rejected_before_importing_model(self):
        for n in (0,5,True):
            with self.assertRaises(ValueError):create_recognizer('unused',num_hands=n)
        for n in (-1,3,True):
            with self.assertRaises(ValueError):create_recognizer('unused',cpu_threads=n)

if __name__=='__main__':unittest.main()
