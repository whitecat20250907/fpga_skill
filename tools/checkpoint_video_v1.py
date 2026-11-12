"""Commit the verified video baseline without capturing active merge/game work."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

R=Path(__file__).resolve().parents[1];Y=R/'projects/twb_feature_integration_20261023'
O=Y/'evidence/video_checkpoint_v1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def git(*args,**kw):return subprocess.run(['git','-c','core.autocrlf=false',*args],cwd=R,capture_output=True,check=True,**kw).stdout

def main():
    assert not O.exists()
    before_index=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    files={Path(__file__),R/'CURRENT_CAMERA.json',R/'TASK_SCHEDULING.json',R/'PENDING_TASK_ESTIMATES.json',
        R/'PENDING_TASKS.md',R/'PENDING_TASKS.json',R/'PENDING_FIELD_TESTS.md',R/'PENDING_FIELD_TESTS.json',
        R/'tools/refresh_pending_tasks.py',R/'tools/publish_video_priority_v1.py',
        R/'tools/publish_video_running_v1.py',R/'tools/publish_video_human_v1.py',
        R/'skills/anlogic-td-demo-reuse/references/ui-camera-coexistence.md'}
    skip={'.vvp','.bit','.pyc','.exe','.db','.lic','.env','.logw'}
    for p in Y.rglob('*'):
        if not p.is_file() or p.suffix in skip:continue
        relative=p.relative_to(Y)
        if relative.parts[0]=='game_integration' or '__pycache__' in relative.parts:continue
        assert p.stat().st_size<8_000_000,p
        files.add(p)
    progress=json.loads((R/'GOAL_PROGRESS.json').read_text(encoding='utf8'))
    ledger=Path(progress['full_task_ledger']['path']);assert sha(ledger)==progress['full_task_ledger']['sha256']
    assert json.loads(ledger.read_text(encoding='utf8'))['revision']==254
    for revision in (252,253,254):
        base=ledger.parent.parent/f'goal_task_ledger_v{revision}'
        files.update(p for p in base.iterdir() if p.is_file())
    O.mkdir();snapshot=O/'GOAL_PROGRESS_snapshot.json';snapshot.write_bytes((R/'GOAL_PROGRESS.json').read_bytes());files.add(snapshot)
    assert not before_index&{p.relative_to(R).as_posix() for p in files},'An owned file already has staged changes; preserve them'
    rows=[dict(path=p.relative_to(R).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    save(O/'files.json',dict(status='OWNED_VERIFIED_VIDEO_BASELINE',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files=rows,full_goal_complete=False,omitted='Active game_integration, other chat projects, copied bit images and simulator caches; existing untracked GOAL_PROGRESS preserved as a snapshot.',
        intentional_binary='SHA-pinned ARM sender shared library and regular-member deployment source archive; no credentials or license files.'))
    rows.append(dict(path=(O/'files.json').relative_to(R).as_posix(),size=(O/'files.json').stat().st_size,sha256=sha(O/'files.json')))
    paths=[x['path'] for x in rows];pathfile=O/'paths.nul';pathfile.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0')
    git('add','--force','--pathspec-from-file='+str(pathfile),'--pathspec-file-nul')
    raw=git('cat-file','--batch',input=b''.join((':'+p+'\n').encode() for p in paths));pos=0
    for row in rows:
        end=raw.index(b'\n',pos);header=raw[pos:end].split();assert header[1]==b'blob'
        n=int(header[2]);pos=end+1;body=raw[pos:pos+n];pos+=n
        assert raw[pos:pos+1]==b'\n';pos+=1
        assert n==row['size'] and hashlib.sha256(body).hexdigest()==row['sha256'],row['path']
        assert sha(R/row['path'])==row['sha256'],row['path']
    assert pos==len(raw)
    p=subprocess.run(['git','-c','core.autocrlf=false','-c','user.name=Codex','-c','user.email=codex@local.invalid','commit','--only',
        '--pathspec-from-file='+str(pathfile),'--pathspec-file-nul','-m',
        'Deploy real hand head eye digital twin and verify live board video baseline'],cwd=R,capture_output=True)
    (O/'commit.stdout').write_bytes(p.stdout);(O/'commit.stderr').write_bytes(p.stderr);assert p.returncode==0,p.stderr.decode(errors='replace')
    commit=git('rev-parse','HEAD').decode().strip()
    changed=set(filter(None,git('diff-tree','--no-commit-id','--name-only','-r','-z',commit).decode().split('\0')))
    assert changed<=set(paths)
    after_index=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    assert before_index<=after_index,'Unrelated staged file removed'
    result=dict(status='EXACT_VIDEO_BASELINE_COMMITTED',commit=commit,files=len(paths),changed_files=len(changed),
        unrelated_index_paths_preserved=sorted(before_index),full_goal_complete=False)
    save(O/'commit_verification.json',result);print(json.dumps(result))

if __name__=='__main__':main()
