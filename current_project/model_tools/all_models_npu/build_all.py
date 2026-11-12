"""Sequential isolated compiler jobs, durable result after every model."""
import json, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PY='/userdata/gaze_model_migration_v1_20261014/venv/bin/python'
rows=[]
for name in ['canned_gesture_classifier','gesture_embedder','face_detector','hand_detector','face_landmarks_detector','hand_landmarks_detector','face_blendshapes']:
    row=dict(name=name,steps=[])
    for script in ['tflite_to_onnx.py','convert_model.py']:
        log=ROOT/(name+'.'+script+'.log');start=time.time()
        with log.open('w') as f:
            result=subprocess.run([PY,str(ROOT/script),name],stdout=f,stderr=subprocess.STDOUT,timeout=600)
        row['steps'].append(dict(script=script,returncode=result.returncode,seconds=time.time()-start,log=log.name))
        if result.returncode:break
    rows.append(row);(ROOT/'build_results.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(row),flush=True)
if any(len(row['steps'])!=2 or any(s['returncode'] for s in row['steps']) for row in rows):
    raise SystemExit('Build failed; inspect build_results.json and individual logs')
