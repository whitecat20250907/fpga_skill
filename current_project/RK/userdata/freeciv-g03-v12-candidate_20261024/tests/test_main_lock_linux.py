"""No models/cameras: verify the optional entry shares the existing file lock."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_main_with_freeciv import existing_main_lock


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux flock contract')
class MainLock(unittest.TestCase):
    def test_duplicate_refused_and_lock_released(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/'app_v28';directory.mkdir()
            with existing_main_lock(directory):
                with self.assertRaisesRegex(RuntimeError,'Existing main instance'):
                    with existing_main_lock(directory):self.fail('Duplicate main was allowed')
            with existing_main_lock(directory):pass

    def test_lock_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/'app_v28';directory.mkdir()
            target=Path(temp)/'other';target.write_text('preserve')
            (Path(temp)/'gaze.lock').symlink_to(target)
            with self.assertRaises(OSError):
                with existing_main_lock(directory):self.fail('Symlink lock accepted')
            self.assertEqual(target.read_text(),'preserve')


if __name__=='__main__':unittest.main()
