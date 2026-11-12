"""Save exact owned application candidates/proofs without staging other work."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

R=Path(__file__).resolve().parents[1];Y=R/'projects/twb_feature_integration_20261023'
O=Y/'evidence/application_checkpoint_v1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def git(*args,**kw):return subprocess.run(['git','-c','core.autocrlf=false',*args],cwd=R,capture_output=True,check=True,**kw).stdout

def main():
    assert not O.exists()
    before_index=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    files={Path(__file__),R/'CURRENT_CAMERA.json',R/'PENDING_TASKS.md',R/'PENDING_TASKS.json',
        R/'PENDING_FIELD_TESTS.md',R/'PENDING_FIELD_TESTS.json',R/'TASK_SCHEDULING.json',R/'PENDING_TASK_ESTIMATES.json',
        R/'tools/publish_app_ui_scope_v1.py',R/'tools/publish_application_progress_v1.py',R/'tools/publish_tdm_ui_sources_v1.py',
        R/'skills/anlogic-td-demo-reuse/references/hft-ui-panel-cold-start.md',
        Y/'README.md',Y/'BOARD_VIDEO_REPORT.md',Y/'APP_UI_REDESIGN.md',Y/'tdm_profile_lessons_v1.md'}
    roots=[Y/'ui_app_v1',Y/'app_relay_v1',Y/'handoff',
        *[Y/'evidence'/name for name in ('hft2_app_v1','app_scene_v1','app_scene_v2','owner_app_session_v1','owner_app_session_v2',
            'app_raster_v1','app_raster_v2','app_raster_v3','app_raster_v4','successor_actual_v1','tdm_profile_actual_v1')]]
    skip={'.vvp','.ppm','.exe','.bit','.db','.lic','.env','.pyc','.so','.dll','.o','.a','.zip'}
    for base in roots:
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix in skip or '__pycache__' in path.parts:continue
            # The new application owner is actively being implemented by its
            # agent; it is intentionally saved in a later verified checkpoint.
            if path.is_relative_to(Y/'handoff/profile_app_v1'):continue
            assert path.stat().st_size<8_000_000,path
            files.add(path)
    for name in ('prepare_app_raster_v1.py','verify_app_raster_v1.py','prepare_hft2_rtl_v1.py','prepare_hft2_native_v1.py',
                 'verify_hft2_app_v1.py','test_app_scene_v1.py','test_owner_app_session_v1.py'):
        files.add(Y/'tools'/name)
    progress=json.loads((R/'GOAL_PROGRESS.json').read_text(encoding='utf8'));ledger=Path(progress['full_task_ledger']['path'])
    assert sha(ledger)==progress['full_task_ledger']['sha256']
    assert json.loads(ledger.read_text())['revision']==257
    for revision in (255,256,257):files.update(p for p in (ledger.parent.parent/f'goal_task_ledger_v{revision}').iterdir() if p.is_file())
    O.mkdir();snapshot=O/'GOAL_PROGRESS_snapshot.json';snapshot.write_bytes((R/'GOAL_PROGRESS.json').read_bytes());files.add(snapshot)
    assert not before_index&{p.relative_to(R).as_posix() for p in files},'Existing owned staged content is preserved; inspect before committing'
    rows=[dict(path=p.relative_to(R).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    save(O/'files.json',dict(status='OWNED_APPLICATION_CANDIDATES_AND_REAL_TDM_RECOVERY',files=rows,
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),full_goal_complete=False,
        omitted='Active profile_app_v1, other-chat project modifications, existing shared SKILL edits, simulator caches, models and executable libraries. Shared SKILL index remains intact in the working tree.',
        acceptance='UI/host contracts are local. Native TDM bytes passed; app37 startup failed before model. Formal full video restored; no new UI hardware/human acceptance.'))
    rows.append(dict(path=(O/'files.json').relative_to(R).as_posix(),size=(O/'files.json').stat().st_size,sha256=sha(O/'files.json')))
    paths=[row['path'] for row in rows];pathfile=O/'paths.nul';pathfile.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0')
    git('add','--force','--pathspec-from-file='+str(pathfile),'--pathspec-file-nul')
    raw=git('cat-file','--batch',input=b''.join((':'+p+'\n').encode() for p in paths));pos=0
    for row in rows:
        end=raw.index(b'\n',pos);header=raw[pos:end].split();assert header[1]==b'blob'
        n=int(header[2]);pos=end+1;body=raw[pos:pos+n];pos+=n;assert raw[pos:pos+1]==b'\n';pos+=1
        assert n==row['size'] and hashlib.sha256(body).hexdigest()==row['sha256'],row['path']
        assert sha(R/row['path'])==row['sha256'],row['path']
    assert pos==len(raw)
    cmd=['git','-c','core.autocrlf=false','-c','user.name=Codex','-c','user.email=codex@local.invalid','commit','--only',
        '--pathspec-from-file='+str(pathfile),'--pathspec-file-nul','-m',
        'Implement HFT2 application UI and record native TDM tests with full video recovery','-m',
        'Freeze the tested renderer, registered actor/trajectory/game bridge, ARM sources and real transaction evidence. Keep the app37 startup failure and pending new-UI hardware/human acceptance explicit.']
    p=subprocess.run(cmd,cwd=R,capture_output=True)
    (O/'commit.stdout').write_bytes(p.stdout);(O/'commit.stderr').write_bytes(p.stderr);assert p.returncode==0,p.stderr.decode(errors='replace')
    commit=git('rev-parse','HEAD').decode().strip();changed=set(filter(None,git('diff-tree','--no-commit-id','--name-only','-r','-z',commit).decode().split('\0')))
    assert changed<=set(paths)
    after_index=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    assert before_index<=after_index
    result=dict(status='EXACT_APPLICATION_SOURCE_CHECKPOINT_COMMITTED',commit=commit,files=len(paths),changed_files=len(changed),
        previous_staged_paths_preserved=sorted(before_index),full_goal_complete=False)
    save(O/'commit_verification.json',result);print(json.dumps(result))

if __name__=='__main__':main()
