"""Optional existing-face-result export. Run instead of the original main;
the existing main lock is mandatory. Original source/models stay untouched.
"""
import argparse,importlib.util,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from run_main_with_freeciv import existing_main_lock
from project_features import FeaturePublisher,face_features
def main():
    ap=argparse.ArgumentParser(add_help=False);ap.add_argument('--app-dir',type=Path,required=True)
    ap.add_argument('--feature-port',type=int,default=29802);options,args=ap.parse_known_args()
    directory=options.app_dir.resolve(strict=True)
    with existing_main_lock(directory):
        os.chdir(directory);sys.path.insert(0,str(directory));sys.path.insert(0,str(directory/'GazeFollower'))
        publisher=FeaturePublisher(('127.0.0.1',options.feature_port),fps=10)
        from gazefollower.face_alignment import MediaPipeFaceAlignment
        original=MediaPipeFaceAlignment.detect
        def observed(self,timestamp,bgr,**kwargs):
            face=original(self,timestamp,bgr,**kwargs)
            if publisher.due():
                try:publisher.send(face_features(face,timestamp,publisher.sequence))
                except (ValueError,TypeError,AttributeError):publisher.dropped+=1
            return face
        MediaPipeFaceAlignment.detect=observed
        try:
            path=directory/'run_gaze.py';spec=importlib.util.spec_from_file_location('_existing_feature_main',path)
            module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
            sys.argv=[str(path),*args];module.main()
        finally:MediaPipeFaceAlignment.detect=original;publisher.close()
if __name__=='__main__':main()
