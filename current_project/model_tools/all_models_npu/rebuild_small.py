import subprocess,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for name in ['gesture_embedder','face_blendshapes']:
    for script in ['tflite_to_onnx.py','convert_model.py']:
        with (ROOT/(name+'.placement_fix.'+script+'.log')).open('w') as f:
            p=subprocess.run([sys.executable,str(ROOT/script),name],stdout=f,stderr=subprocess.STDOUT,timeout=300)
        if p.returncode:raise RuntimeError((script,name,p.returncode))
    print(name,'BUILT',flush=True)
