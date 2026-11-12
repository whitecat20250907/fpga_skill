"""Checkpoint actual v4a recovery, retained control defect and standalone v12."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

R=Path(__file__).resolve().parents[1]
Y=R/'projects/twb_feature_integration_20261023'
O=Y/'evidence/v4a_running_checkpoint_v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def git(*args,**kwargs):
    return subprocess.run(['git','-c','core.autocrlf=false',*args],cwd=R,capture_output=True,check=True,**kwargs).stdout

def main():
    assert not O.exists()
    current=json.loads((R/'CURRENT_CAMERA.json').read_text())
    assert current['status']=='POINTER_ACTUAL_APP39_V4A_RUNNING_CONTROL_REPAIR_PENDING'
    assert sha(current['selection']['path'])==current['selection']['sha256']
    bound=json.loads((Y/'evidence/application_recovery_actual_v6/binding.json').read_text())
    assert bound['owner']['pid']==250418 and bound['owner']['start_ticks']==67336261
    assert bound['control_config_runtime_mutation_detected'] and not bound['interaction_control_accepted']
    assert sha(Y/'evidence/application_recovery_actual_v6/binding.json')=='d2f6a001f6d01fc5a6eb0db8cb917a6bd1a1c960bf1f2f04cfb0a56263fab32a'
    staged=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    names=['CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json',
           'TASK_SCHEDULING.json','PENDING_TASK_ESTIMATES.json','tools/publish_app39_recovery_v4a_running_v1.py',
           'tools/publish_game_v12_supplemental_v1.py','projects/twb_feature_integration_20261023/README.md',
           'projects/twb_feature_integration_20261023/BOARD_VIDEO_REPORT.md',
           'projects/twb_feature_integration_20261023/video_delivery/README.md',
           'skills/anlogic-td-demo-reuse/references/hft2-live-integration.md',
           'skills/anlogic-td-demo-reuse/references/recovery-state-ownership-20261024.md']
    files={Path(__file__),*(R/n for n in names)}
    roots=[Y/'evidence/application_recovery_actual_v5',Y/'evidence/application_recovery_actual_v6',
           Y/'handoff/normal_empty_v4a_exit_v1',
           R/'projects/pcie_imx415_bar_contract37_20261010/evidence/game_v12_supplemental_dry_review_v1']
    files.update(Y/'tools'/name for name in (
        'execute_application_recovery_actual_v5.py','execute_application_recovery_actual_v6.py',
        'diagnose_recovery_v5_source_closure.py','collect_recovery_v5_full_ancestry.py',
        'collect_recovery_v6_exit_original.py','bind_application_recovery_actual_v6.py',
        'collect_recovery_v6_original_chain.py','collect_recovery_v6_original_chain_v2.py',
        'stage_app40_sourceonly_v2.py','install_app40_sourceonly_v2.py',
        'settle_app40_source_permissions_v1.py','settle_app40_source_permissions_v2.py'))
    omitted=[];raw=[]
    omit={'.vvp','.bit','.exe','.pyc','.bin','.rgb','.ppm','.hex','.rknn','.mnn','.task','.onnx','.tflite','.zip','.ko','.gz'}
    for root in roots:
        assert root.is_dir(),root
        for p in sorted(root.rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts:continue
            if 'longrun_35min_v4a' in p.parts and p.name not in ('measurement_sources.json','first_snapshot.json','bounded_longrun_snapshot.sh'):
                continue  # Ongoing observer state is mutable, never freeze a racing last snapshot.
            row=dict(path=p.relative_to(R).as_posix(),sha256=sha(p),size=p.stat().st_size)
            if p.suffix in omit or row['size']>=8_000_000:omitted.append(row);continue
            if re.fullmatch(r'\d{3}\.json',p.name):
                raw.append(row);siblings=sorted(p.parent.glob('[0-9][0-9][0-9].json'))
                if p not in siblings[:1]+siblings[-1:]:continue
            files.add(p)
    progress=json.loads((R/'GOAL_PROGRESS.json').read_text(encoding='utf8'))
    ledger=Path(progress['full_task_ledger']['path']);assert sha(ledger)==progress['full_task_ledger']['sha256']
    assert json.loads(ledger.read_text())['revision']==273
    for n in (272,273):files.update(p for p in (ledger.parent.parent/f'goal_task_ledger_v{n}').iterdir() if p.is_file())
    O.mkdir()
    snapshot=O/'GOAL_PROGRESS_snapshot.json';snapshot.write_bytes((R/'GOAL_PROGRESS.json').read_bytes());files.add(snapshot)
    save(O/'raw_snapshot_index.json',dict(files=raw,scope='All raw observations remain local; first/last bodies and complete SHA index committed.'))
    files.add(O/'raw_snapshot_index.json')
    rows=[dict(path=p.relative_to(R).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    save(O/'files.json',dict(status='APP39_V4A_RUNNING_CONTROL_DEFECT_AND_V12_GAME_CHECKPOINT',
        files=rows,omitted_local_artifacts=omitted,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='Only root-owned Y receipts, v272/v273, two owned references and task views. Excludes P, shared SKILL, live observer moving files, RTL/TD and user edits.',
        restored_running=True,control_accepted=False,longrun_accepted=False,human_accepted=False,full_goal_complete=False))
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
        '-m','Save actual v4a recovery, control defect and standalone v12 acceptance',
        '-m','Record exact empty-owner exit, full poll-thread quiescence, tensor/RGB checks, running app39 and immutable raw proofs. Preserve shared-config control defect, partial failures and pending longrun/human/newbit boundaries. G03 is accepted only for tested v12.'],cwd=R,capture_output=True)
    (O/'commit.stdout').write_bytes(proc.stdout);(O/'commit.stderr').write_bytes(proc.stderr)
    assert proc.returncode==0,proc.stderr.decode(errors='replace')
    commit=git('rev-parse','HEAD').decode().strip()
    changed=set(filter(None,git('diff-tree','--no-commit-id','--name-only','-r','-z',commit).decode().split('\0')))
    assert changed<=selected
    after=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')));assert staged<=after
    result=dict(status='OWNED_V4A_RUNNING_AND_V12_CHECKPOINT_COMMITTED',commit=commit,selected_files=len(selected),changed_files=len(changed),previous_staged_paths_preserved=sorted(staged),full_goal_complete=False)
    save(O/'commit_verification.json',result);print(json.dumps(result))

if __name__=='__main__':main()
