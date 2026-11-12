"""Pin the authoritative graph/calculator semantics used by this port."""
from pathlib import Path
import hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parent/'upstream_reference';ROOT.mkdir(exist_ok=True)
base='https://raw.githubusercontent.com/google-ai-edge/mediapipe/v0.10.18/mediapipe/'
paths=['tasks/cc/vision/gesture_recognizer/calculators/landmarks_to_matrix_calculator.cc','tasks/cc/vision/gesture_recognizer/calculators/handedness_to_matrix_calculator.cc','modules/hand_landmark/calculators/hand_landmarks_to_rect_calculator.cc','calculators/tensor/image_to_tensor_converter_opencv.cc']
rows=json.loads((ROOT/'manifest.json').read_text()) if (ROOT/'manifest.json').exists() else []
for p in paths:
    try:
        b=urllib.request.urlopen(base+p,timeout=20).read();(ROOT/Path(p).name).write_bytes(b)
        rows.append(dict(url=base+p,file=Path(p).name,sha256=hashlib.sha256(b).hexdigest()))
    except Exception as e:rows.append(dict(url=base+p,error=str(e)))
(ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
