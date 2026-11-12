"""Commit only this turn's task views and independent transport evidence."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

R=Path(__file__).resolve().parents[1];S=R/'projects/rgb_area3_stream_20261022'
O=S/'evidence/task_views_transport_checkpoint_v1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def git(*args,**kw):return subprocess.run(['git',*args],cwd=R,capture_output=True,check=True,**kw).stdout


def main():
    assert not O.exists() and git('diff','--cached','--name-only','-z')==b'','Preserve an existing index'
    files={Path(__file__),R/'AGENTS.md',R/'PROJECT_SCOPE.md',R/'TASK_SCHEDULING.json',
        R/'tools/refresh_pending_tasks.py',R/'tools/reorganize_task_views_20261023.py',
        R/'tools/publish_transport_and_task_views_20261023.py',R/'PENDING_TASKS.md',R/'PENDING_TASKS.json',
        R/'PENDING_FIELD_TESTS.md',R/'PENDING_FIELD_TESTS.json',R/'PENDING_TASK_ESTIMATES.json',
        S/'README.md',S/'INTEGRATION_CONTRACT.md',
        R/'skills/anlogic-td-demo-reuse/references/ui-camera-coexistence.md'}
    for name in ('verify_existing_branch_metadata_v1.py','verify_existing_branch_metadata_v2.py','verify_a3f1_guard_v1.py'):
        files.add(S/'tools'/name)
    for name in ('tb_existing_branch_metadata_v1.sv','tb_existing_branch_metadata_v2.sv'):
        files.add(S/'sim'/name)
    files.update(p for p in (S/'transport').rglob('*') if p.is_file())
    prefixes=('existing_branch_metadata_v1','existing_branch_metadata_v2','a3f1_host_guard_v1','dual_stream_readonly_audit_v1')
    suffixes={'.v','.sv','.h','.c','.py','.json','.md','.txt','.stdout','.stderr','.log','.mem','.hex','.patch'}
    for name in prefixes:
        for p in (S/'evidence'/name).rglob('*'):
            if p.is_file() and p.suffix in suffixes and p.stat().st_size<8_000_000:files.add(p)
    files.add(S/'evidence/a3f1_host_guard_v1/actual_RTL_packet.bin')
    progress=json.loads((R/'GOAL_PROGRESS.json').read_text());ledger=Path(progress['full_task_ledger']['path'])
    assert sha(ledger)==progress['full_task_ledger']['sha256'] and json.loads(ledger.read_text())['revision']==250
    for rev in (249,250):
        files.update(p for p in (ledger.parent.parent/f'goal_task_ledger_v{rev}').iterdir() if p.is_file())
    O.mkdir();snapshot=O/'GOAL_PROGRESS_snapshot.json';snapshot.write_bytes((R/'GOAL_PROGRESS.json').read_bytes());files.add(snapshot)
    files={p.resolve() for p in files}
    assert all(p.is_relative_to(R) and p.is_file() and p.stat().st_size<15_000_000 for p in files)
    assert not any(p.suffix in ('.lic','.env','.exe','.db','.dmp','.vvp') for p in files)
    rows=[dict(path=p.relative_to(R).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    save(O/'files.json',dict(status='OWNED_TWO_TASK_VIEWS_AND_INDEPENDENT_EXISTING_TRANSPORT_CHECKPOINT',
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=rows,
        omitted='Other active native/hardware transaction, volatile root pointers, unrelated edits, raw DBs/executables, regenerable large RGB files and simulator caches.',
        full_goal_complete=False))
    paths=[x['path'] for x in rows]+[(O/'files.json').relative_to(R).as_posix()]
    (O/'paths.nul').write_bytes(b'\0'.join(x.encode() for x in paths)+b'\0')
    git('add','--force','--pathspec-from-file='+str(O/'paths.nul'),'--pathspec-file-nul')
    staged=set(filter(None,git('diff','--cached','--name-only','-z').decode().split('\0')))
    assert staged and staged<=set(paths)
    pins={x['path']:x for x in rows};pins[paths[-1]]=dict(path=paths[-1],size=(O/'files.json').stat().st_size,sha256=sha(O/'files.json'))
    raw=git('cat-file','--batch',input=b''.join((':'+p+'\n').encode() for p in paths));pos=0
    for path in paths:
        end=raw.index(b'\n',pos);header=raw[pos:end].split();assert header[1]==b'blob'
        length=int(header[2]);pos=end+1;body=raw[pos:pos+length];pos+=length
        assert raw[pos:pos+1]==b'\n';pos+=1
        assert length==pins[path]['size'] and hashlib.sha256(body).hexdigest()==pins[path]['sha256'],path
    assert pos==len(raw)
    for row in rows:assert sha(R/row['path'])==row['sha256'],row['path']
    p=subprocess.run(['git','-c','user.name=Codex','-c','user.email=codex@local.invalid','commit','-m',
        'Separate implementation and field-test tasks; defer RK CSI and harden A3F1 intake'],cwd=R,capture_output=True)
    (O/'commit.stdout').write_bytes(p.stdout);(O/'commit.stderr').write_bytes(p.stderr);assert p.returncode==0
    commit=git('rev-parse','HEAD').decode().strip()
    save(O/'commit_verification.json',dict(status='EXACT_OWNED_INDEX_BLOBS_VERIFIED_AND_COMMITTED',commit=commit,
        files=len(paths),changed_files=len(staged),full_goal_complete=False))
    print(json.dumps(dict(status='COMMITTED_OWNED_TASK_VIEWS_AND_TRANSPORT_CHECKS',commit=commit,files=len(paths),changed_files=len(staged))))


if __name__=='__main__':main()
