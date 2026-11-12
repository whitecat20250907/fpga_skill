"""Read-only evidence after migration; does not signal any process."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import time

root=Path(__file__).resolve().parent
app=Path('/userdata/gaze_model_migration_v1_20261014/app_v28')
report=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),owners=[],files={})
for pid in [118016,118079]:
    p=Path('/proc')/str(pid)
    report['owners'].append(dict(pid=pid,start_ticks=int((p/'stat').read_text().rsplit(')',1)[1].split()[19]),cwd=str((p/'cwd').resolve())))
for name in ['pcie_capture.py','gaze_runtime.py','run_gaze.py','settings.json',
             'GazeFollower/gazefollower/face_alignment/MediaPipeFaceAlignment.py',
             'GazeFollower/gazefollower/gaze_estimator/RKNNGazeEstimator.py',
             'GazeFollower/gazefollower/res/model_weights/original_gaze_fp16.rknn']:
    report['files'][name]=hashlib.sha256((app/name).read_bytes()).hexdigest()
for fd in (Path('/proc/118016/fd')).iterdir():
    try:
        path=Path(os.readlink(fd))
        if path.suffix!='.csv' or not path.is_file():continue
        with path.open('rb') as stream:
            header=stream.readline().decode()
            stream.seek(max(stream.tell(),path.stat().st_size-120000))
            stream.readline()
            tail=stream.read().decode(errors='replace').splitlines()[-100:]
        rows=list(csv.DictReader(io.StringIO(header+'\n'.join(tail))))
        stamps=[int(r['timestamp_ns']) for r in rows if r.get('timestamp_ns','').isdigit()]
        report['recent_csv']=dict(path=str(path),rows=len(rows),
            valid=sum(r.get('valid') in ('1','True') for r in rows),
            npu_called=sum(r.get('npu_called') in ('1','True') for r in rows),
            last_source_age_seconds=(time.monotonic_ns()-max(stamps))/1e9 if stamps else None)
    except OSError:continue
(root/'evidence/runtime_after.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
