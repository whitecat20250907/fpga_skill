"""Checkpoint only owned task views, ARM component package and RTL candidates."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

R=Path(__file__).resolve().parents[1]
S=R/'projects/rgb_area3_stream_20261022'
O=S/'evidence/task_views_transport_checkpoint_v2'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def git(*args,**kw):return subprocess.run(['git',*args],cwd=R,capture_output=True,check=True,**kw).stdout


def main():
    assert not O.exists() and git('diff','--cached','--name-only','-z')==b'','Preserve an existing index'
    files={Path(__file__),R/'PROJECT_SCOPE.md',R/'TASK_SCHEDULING.json',R/'PENDING_TASK_ESTIMATES.json',
        R/'PENDING_TASKS.md',R/'PENDING_TASKS.json',R/'PENDING_FIELD_TESTS.md',R/'PENDING_FIELD_TESTS.json',
        R/'tools/publish_arm_components_and_task_views_v1.py',S/'README.md',
        R/'skills/anlogic-td-demo-reuse/references/ui-camera-coexistence.md'}
    tools=(
        'collect_guarded_receiver_ARM_v1.py','prepare_guarded_receiver_v1.py',
        'run_guarded_receiver_build_ARM_v1.py','run_guarded_worker_ARM_v1.py','test_worker_guarded_prepare_v1.py',
        'verify_source_bound_nonce_credit_v1.py','verify_source_bound_nonce_credit_v2.py',
        'verify_source_bound_nonce_credit_v3.py','verify_nonce_integration_patch_v1.py',
    )
    files.update(S/'tools'/n for n in tools)
    sim=('tb_source_bound_epoch_branch_v1.sv','tb_source_bound_epoch_branch_v2.sv',
        'tb_source_bound_nonce_credit_v1.sv','tb_source_bound_nonce_credit_v2.sv')
    files.update(S/'sim'/n for n in sim)
    allowed={'.v','.sv','.h','.c','.py','.json','.md','.txt','.stdout','.stderr','.log','.mem','.hex','.patch','.bin','.sha256','.al'}
    for p in (S/'transport').rglob('*'):
        if p.is_file() and (p.suffix in allowed or p.name=='manifest.sha256'):files.add(p)
    files.update(p for p in (S/'delivery/a3f1_guarded_receiver_v1').rglob('*') if p.is_file())
    prefixes=(
        'a3f1_receiver_build_ARM_v1','guarded_worker_ARM_v1','a3f1_ARM_artifacts_v1','test_worker_guarded_preparation_v1',
        'source_bound_nonce_credit_v1','source_bound_nonce_credit_v2','source_bound_nonce_credit_v3',
        'preview_source_pairing_v1','preview_eof_loss_v1','preview_source_design_v1',
        'nonce_integration_patch_applied_v1','nonce_integration_patch_applied_v2',
        'a3f1_shutdown_readonly_v1',
    )
    completion_prefixes=tuple(p.name for p in (S/'evidence').glob('preview_completion_meta_v*') if p.is_dir())
    for prefix in prefixes+completion_prefixes:
        base=S/'evidence'/prefix
        if not base.exists():continue
        for p in base.rglob('*'):
            if p.is_file() and (p.suffix in allowed or p.name=='manifest.sha256') and p.stat().st_size<8_000_000:
                files.add(p)
    progress=json.loads((R/'GOAL_PROGRESS.json').read_text(encoding='utf8'))
    ledger=Path(progress['full_task_ledger']['path'])
    assert sha(ledger)==progress['full_task_ledger']['sha256'] and json.loads(ledger.read_text(encoding='utf8'))['revision']==251
    files.update(p for p in ledger.parent.iterdir() if p.is_file())
    O.mkdir()
    snapshot=O/'GOAL_PROGRESS_snapshot.json';snapshot.write_bytes((R/'GOAL_PROGRESS.json').read_bytes());files.add(snapshot)
    files={p.resolve() for p in files}
    assert all(p.is_relative_to(R) and p.is_file() and p.stat().st_size<15_000_000 for p in files)
    assert not any(p.suffix in ('.lic','.env','.exe','.db','.dmp','.vvp') for p in files)
    rows=[dict(path=p.relative_to(R).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    save(O/'files.json',dict(status='OWNED_COMPONENTS_AND_SEPARATED_TASK_VIEWS',
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=rows,
        omitted='Unrelated dirty files, other owner live project/CURRENT, raw native DBs, simulator caches and large regenerable RGB output.',
        intentional_binaries='Three SHA-verified AArch64 delivery binaries; protocol fixtures and candidate zip/source tar.',
        default_app_or_FPGA_changed=False,full_goal_complete=False))
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
        'Record ARM receiver components and preserve separate implementation and field-test queues'],cwd=R,capture_output=True)
    (O/'commit.stdout').write_bytes(p.stdout);(O/'commit.stderr').write_bytes(p.stderr);assert p.returncode==0
    commit=git('rev-parse','HEAD').decode().strip()
    result=dict(status='EXACT_OWNED_INDEX_BLOBS_VERIFIED_AND_COMMITTED',commit=commit,files=len(paths),changed_files=len(staged),full_goal_complete=False)
    save(O/'commit_verification.json',result);print(json.dumps(result))


if __name__=='__main__':main()
