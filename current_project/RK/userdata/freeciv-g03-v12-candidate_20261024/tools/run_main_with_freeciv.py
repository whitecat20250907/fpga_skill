"""Opt-in app28 adapter using its existing model, environment and bindings.

Run with the original main program's Python and arguments, after closing its
previous instance. No application source or environment is overwritten. An
existing gesture recognizer can call app.freeciv_action(name); no new gesture
recognition or replacement gesture mapping is installed here.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from screen_bridge import FreecivScreenInput


@contextmanager
def existing_main_lock(directory):
    """Share the original gaze.sh lock; reject duplicates before model import."""
    if os.name!='posix':raise RuntimeError('This optional main adapter requires Linux')
    import fcntl
    descriptor=os.open(directory.parent/'gaze.lock',os.O_RDWR|os.O_CREAT|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Existing main instance holds gaze.lock; close it normally before starting the optional adapter') from None
        yield
    finally:os.close(descriptor)


def main():
    ap=argparse.ArgumentParser(description=__doc__,add_help=False)
    ap.add_argument('--app-dir',type=Path,required=True)
    options,original_args=ap.parse_known_args()
    directory=options.app_dir.resolve(strict=True)
    if not (directory/'run_gaze.py').is_file():raise RuntimeError('Original run_gaze.py is required')
    with existing_main_lock(directory):
        previous=Path.cwd()
        try:
            os.chdir(directory)
            run_locked(directory,original_args)
        finally:os.chdir(previous)


def run_locked(directory,original_args):
    source=directory/'run_gaze.py'
    if not source.is_file():raise RuntimeError('Original run_gaze.py is required')
    sys.path.insert(0,str(directory))
    spec=importlib.util.spec_from_file_location('_existing_gaze_main',source)
    original=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=original
    spec.loader.exec_module(original)
    base=original.App

    class AppWithFreeciv(base):
        def __init__(self,settings):
            super().__init__(settings)
            self.freeciv=FreecivScreenInput()
            self.freeciv_action=self.freeciv.action
            self.freeciv_held_action=self.freeciv.held_action

        def process(self,samples):
            super().process(samples)
            self.freeciv.update()
            sample=self.latest_sample
            if (samples and sample and sample['valid'] and self.phase=='TRACK'
                and self.last_gaze is not None and self.calibration is not None
                and self.calibration.has_calibrated):
                # last_gaze is the continuous filtered coordinate BEFORE the
                # original app's optional region/grid cursor calculation.
                x,y=map(float,self.last_gaze)
                self.freeciv.gaze_screen(x+self.geometry['x'],y+self.geometry['y'],sample['t'])
            elif samples:
                self.freeciv.invalidate_gaze()

        def run(self):
            try:return super().run()
            finally:self.freeciv.close()

    original.App=AppWithFreeciv
    sys.argv=[str(source),*original_args]
    original.main()


if __name__=='__main__':main()
