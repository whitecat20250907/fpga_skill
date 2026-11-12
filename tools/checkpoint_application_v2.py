"""Commit exact owned third-generation source/proofs; preserve other work."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

R=Path(__file__).resolve().parents[1];Y=R/'projects/twb_feature_integration_20261023'
O=Y/'evidence/application_checkpoint_v2'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def git(*args,**kw):return subprocess.run(['git','-c','core.autocrlf=false',*args],cwd=R,capture_output=True,check=True,**kw).stdout


def main():
    assert not O.exists()
    staged=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    files={Path(__file__),R/'CURRENT_CAMERA.json',R/'PENDING_TASKS.md',R/'PENDING_TASKS.json',
        R/'PENDING_FIELD_TESTS.md',R/'PENDING_FIELD_TESTS.json',R/'TASK_SCHEDULING.json',R/'PENDING_TASK_ESTIMATES.json',
        R/'tools/publish_hft2_actual_failures_v1.py',R/'tools/publish_application_runtime_failure_v1.py',
        R/'tools/publish_application_live_v3_progress.py',R/'tools/publish_recruit_measurement_progress_v1.py',Y/'README.md',Y/'BOARD_VIDEO_REPORT.md',
        R/'skills/anlogic-td-demo-reuse/references/hft-ui-panel-cold-start.md',
        R/'skills/anlogic-td-demo-reuse/references/hft2-live-integration.md'}
    roots=[Y/'tools',Y/'ui_app_v1',Y/'handoff/profile_app_v1',Y/'handoff/profile_app_v2']
    roots += [p for p in (Y/'evidence').iterdir() if p.is_dir() and (p.name.startswith('application_') or p.name in ('inactive_hft2_host_v1','sgdma_closed_state_v2','passive_measurement_v2')) and p!=O]
    skip={'.vvp','.ppm','.exe','.bit','.db','.lic','.env','.pyc','.so','.dll','.o','.a','.zip','.rknn','.onnx','.pt','.pth','.tflite','.bin','.sdf','.ko'}
    omitted=[]
    for root in roots:
        if not root.exists():continue
        samples=sorted(root.glob('[0-9][0-9][0-9].json'))
        endpoints=set(samples[:1]+samples[-1:])
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix in skip or '__pycache__' in path.parts:continue
            # Bounded raw snapshots remain on disk; commit each window's
            # endpoints, result, source pins and exact raw-file hash index.
            if re.fullmatch(r'\d{3}\.json',path.name):
                siblings=sorted(path.parent.glob('[0-9][0-9][0-9].json'))
                if path not in siblings[:1]+siblings[-1:]:continue
            if path.stat().st_size>=8_000_000:
                omitted.append(dict(path=str(path.relative_to(R)),size=path.stat().st_size,sha256=sha(path)));continue
            files.add(path)
    progress=json.loads((R/'GOAL_PROGRESS.json').read_text(encoding='utf8'));ledger=Path(progress['full_task_ledger']['path'])
    assert sha(ledger)==progress['full_task_ledger']['sha256']
    revision=json.loads(ledger.read_text())['revision'];assert revision>=261
    for number in range(258,revision+1):
        folder=ledger.parent.parent/f'goal_task_ledger_v{number}'
        if folder.exists():files.update(p for p in folder.iterdir() if p.is_file() and p.stat().st_size<8_000_000)
    O.mkdir();snapshot=O/'GOAL_PROGRESS_snapshot.json';snapshot.write_bytes((R/'GOAL_PROGRESS.json').read_bytes());files.add(snapshot)
    raw=[]
    for root in roots:
        if root.exists():
            for path in sorted(root.rglob('[0-9][0-9][0-9].json')):
                if path.is_file():raw.append(dict(path=path.relative_to(R).as_posix(),size=path.stat().st_size,sha256=sha(path)))
    save(O/'raw_snapshot_index.json',dict(status='EXACT_RAW_SNAPSHOT_INDEX_LOCAL_FILES_PRESERVED',files=raw));files.add(O/'raw_snapshot_index.json')
    relative={p.relative_to(R).as_posix() for p in files};assert not staged&relative
    assert all(p.exists() for p in files)
    rows=[dict(path=p.relative_to(R).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    save(O/'files.json',dict(status='THIRD_APPLICATION_SOURCE_AND_REAL_FAILURE_RECOVERY_STABILITY_CHECKPOINT',files=rows,
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),omitted_large_files=omitted,
        source_scope='Root-owned Y source/proofs and task views only. Other-chat project, credentials, shared SKILL edits, models, binaries and CAD artifacts are excluded. Raw sample intermediate bodies remain on disk and are hash-indexed.',
        acceptance='New9e82/app38 running. Real native tensors/RGB1080 and 13-stage physical pass; visual/trajectory bounded empty-scene tests pass. No new optical/human/eight-stroke/calibration/game-control acceptance. Stale bounded relay log cannot supply later hardware rates.',full_goal_complete=False))
    rows.append(dict(path=(O/'files.json').relative_to(R).as_posix(),size=(O/'files.json').stat().st_size,sha256=sha(O/'files.json')))
    paths=[row['path'] for row in rows];pathfile=O/'paths.nul';pathfile.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0')
    git('add','--force','--pathspec-from-file='+str(pathfile),'--pathspec-file-nul')
    raw=git('cat-file','--batch',input=b''.join((':'+p+'\n').encode() for p in paths));pos=0
    for row in rows:
        end=raw.index(b'\n',pos);header=raw[pos:end].split();assert header[1]==b'blob';size=int(header[2]);pos=end+1
        body=raw[pos:pos+size];pos+=size;assert raw[pos:pos+1]==b'\n';pos+=1
        assert size==row['size'] and hashlib.sha256(body).hexdigest()==row['sha256'] and sha(R/row['path'])==row['sha256'],row['path']
    assert pos==len(raw)
    command=['git','-c','core.autocrlf=false','-c','user.name=Codex','-c','user.email=codex@local.invalid','commit','--only',
        '--pathspec-from-file='+str(pathfile),'--pathspec-file-nul','-m',
        'Deploy HFT2 application with dependency and bounds recovery fixes',
        '-m','Preserve both real failed generations and complete normal recovery; retain the measured third profile and separate implementation readiness from human/optical/game acceptance.']
    result=subprocess.run(command,cwd=R,capture_output=True)
    (O/'commit.stdout').write_bytes(result.stdout);(O/'commit.stderr').write_bytes(result.stderr);assert result.returncode==0,result.stderr.decode(errors='replace')
    commit=git('rev-parse','HEAD').decode().strip();changed=set(filter(None,git('diff-tree','--no-commit-id','--name-only','-r','-z',commit).decode().split('\0')))
    assert changed<=set(paths)
    after=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')));assert staged<=after
    value=dict(status='EXACT_APPLICATION_SOURCE_CHECKPOINT_COMMITTED',commit=commit,files=len(paths),changed_files=len(changed),previous_staged_paths_preserved=sorted(staged),full_goal_complete=False)
    save(O/'commit_verification.json',value);print(json.dumps(value))


if __name__=='__main__':main()
