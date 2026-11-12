"""Checkpoint only root-owned actual second app39 failure and original wait."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

R=Path(__file__).resolve().parents[1]
Y=R/'projects/twb_feature_integration_20261023'
O=Y/'evidence/app39_failure_checkpoint_v2'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def git(*args,**kwargs):
    return subprocess.run(['git','-c','core.autocrlf=false',*args],cwd=R,capture_output=True,check=True,**kwargs).stdout

def main():
    assert not O.exists()
    current=json.loads((R/'CURRENT_CAMERA.json').read_text())
    assert current['status']=='POINTER_ACTUAL_APP39_FAILED_NO_HEALTHY_MODEL'
    assert sha(current['selection']['path'])==current['selection']['sha256']
    audit=json.loads((Y/'evidence/application_recovery_actual_v4/post_ack_resource_audit_original.json').read_text())
    assert audit['owner']['pid']==233963 and audit['owner']['start_ticks']==66678019
    assert audit['normal_runtime_PASS'] is False and audit['native_cleanup_errno']==110
    assert audit['all_children_absent'] and len(audit['kernel_other_matching_tasks'])==8
    assert sha(Y/'evidence/application_recovery_actual_v4/post_ack_resource_audit_original.json')=='0b8ab0536e115e52f0134b26e93b0d4ef7c12fe9fd6bddf39ad9aa4ff51033a0'
    staged=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    names=['CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json',
           'TASK_SCHEDULING.json','PENDING_TASK_ESTIMATES.json','tools/publish_app39_terminal_failure_v1.py',
           'tools/publish_app39_retired_failure_v1.py','projects/twb_feature_integration_20261023/README.md',
           'projects/twb_feature_integration_20261023/BOARD_VIDEO_REPORT.md',
           'projects/twb_feature_integration_20261023/video_delivery/README.md']
    files={Path(__file__),*(R/n for n in names)}
    roots=[Y/'evidence/application_recovery_actual_v4',Y/'evidence/app39_observation_until_human_v1']
    omitted=[];raw=[]
    omit={'.vvp','.bit','.exe','.pyc','.bin','.rgb','.ppm','.hex','.rknn','.mnn','.task','.onnx','.tflite','.zip','.ko'}
    for root in roots:
        assert root.is_dir(),root
        for p in sorted(root.rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts:continue
            row=dict(path=p.relative_to(R).as_posix(),sha256=sha(p),size=p.stat().st_size)
            if p.suffix in omit or row['size']>=8_000_000:omitted.append(row);continue
            if re.fullmatch(r'\d{3}\.json',p.name):
                raw.append(row);siblings=sorted(p.parent.glob('[0-9][0-9][0-9].json'))
                if p not in siblings[:1]+siblings[-1:]:continue
            files.add(p)
    progress=json.loads((R/'GOAL_PROGRESS.json').read_text(encoding='utf8'))
    ledger=Path(progress['full_task_ledger']['path']);assert sha(ledger)==progress['full_task_ledger']['sha256']
    assert json.loads(ledger.read_text())['revision']==271
    for n in (270,271):files.update(p for p in (ledger.parent.parent/f'goal_task_ledger_v{n}').iterdir() if p.is_file())
    O.mkdir()
    snapshot=O/'GOAL_PROGRESS_snapshot.json';snapshot.write_bytes((R/'GOAL_PROGRESS.json').read_bytes());files.add(snapshot)
    save(O/'raw_snapshot_index.json',dict(files=raw,scope='All raw observations remain local; first/last bodies and complete SHA index committed.'))
    files.add(O/'raw_snapshot_index.json')
    rows=[dict(path=p.relative_to(R).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    save(O/'files.json',dict(status='APP39_SECOND_TERMINAL_FAILURE_AND_ORIGINAL_WAIT_CHECKPOINT',
        files=rows,omitted_local_artifacts=omitted,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='Only root-owned Y receipts, v270/v271 and task views. Excludes other-chat P, shared skill, active RTL/TD candidates and user edits.',
        normal_runtime_PASS=False,recovery_performed=False,full_goal_complete=False))
    rows.append(dict(path=(O/'files.json').relative_to(R).as_posix(),size=(O/'files.json').stat().st_size,sha256=sha(O/'files.json')))
    selected={v['path'] for v in rows};assert not selected&staged
    assert not any(p.startswith('projects/model_image_ops_board_20261023/') for p in selected)
    pathfile=O/'paths.nul';pathfile.write_bytes(b'\0'.join(p.encode() for p in sorted(selected))+b'\0')
    git('add','--force','--pathspec-from-file='+str(pathfile),'--pathspec-file-nul')
    for row in rows:
        blob=git('show',':'+row['path'])
        assert len(blob)==row['size'] and hashlib.sha256(blob).hexdigest()==row['sha256']==sha(R/row['path']),row['path']
    proc=subprocess.run(['git','-c','core.autocrlf=false','-c','user.name=Codex','-c','user.email=codex@local.invalid',
        'commit','--only','--pathspec-from-file='+str(pathfile),'--pathspec-file-nul',
        '-m','Preserve second app39 capture failure and original resource retirement',
        '-m','Keep cleanup110, exact original ack/wait, empty supervisor and eight loaded-driver poll threads. Mark current runtime failed without claiming recovery or full acceptance.'],cwd=R,capture_output=True)
    (O/'commit.stdout').write_bytes(proc.stdout);(O/'commit.stderr').write_bytes(proc.stderr)
    assert proc.returncode==0,proc.stderr.decode(errors='replace')
    commit=git('rev-parse','HEAD').decode().strip()
    changed=set(filter(None,git('diff-tree','--no-commit-id','--name-only','-r','-z',commit).decode().split('\0')))
    assert changed<=selected
    after=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')));assert staged<=after
    result=dict(status='OWNED_APP39_FAILURE_COMMITTED',commit=commit,selected_files=len(selected),changed_files=len(changed),previous_staged_paths_preserved=sorted(staged),full_goal_complete=False)
    save(O/'commit_verification.json',result);print(json.dumps(result))

if __name__=='__main__':main()
