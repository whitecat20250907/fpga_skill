"""Extract fixed deployed task bundles; keep every original byte and hash."""
import hashlib, io, json, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SOURCES = [Path('/userdata/gaze_model_migration_v1_20261014/app_v30_eye_20261021/GazeFollower/gazefollower/res/model_weights/face_landmarker.task'), Path('/userdata/freeciv-rk3576-gaze-demo/.gesture-v1/assets/gesture_recognizer.task')]
def sha(b): return hashlib.sha256(b).hexdigest()
def unpack(data, lineage, rows):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            b=z.read(name)
            if name.endswith('.task'): unpack(b,lineage+[name],rows)
            elif name.endswith('.tflite'):
                dst=ROOT/'models'/Path(name).name
                dst.write_bytes(b)
                rows.append(dict(name=dst.stem, source=lineage+[name], sha256=sha(b), bytes=len(b)))
def main():
    (ROOT/'models').mkdir(exist_ok=True)
    rows=[]
    for p in SOURCES: unpack(p.read_bytes(), [str(p)], rows)
    (ROOT/'source_manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows,indent=2))
if __name__=='__main__': main()
