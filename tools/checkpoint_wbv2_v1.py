"""Checkpoint only owned DMA recovery/runtime evidence, preserving other work."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

R = Path(__file__).resolve().parents[1]
Y = R / 'projects/twb_feature_integration_20261023'
O = Y / 'evidence/wbv2_checkpoint_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def git(*args, **kwargs):
    return subprocess.run(['git', '-c', 'core.autocrlf=false', *args], cwd=R,
        capture_output=True, check=True, **kwargs).stdout


def main():
    assert not O.exists()
    current = json.loads((R / 'CURRENT_CAMERA.json').read_text(encoding='utf8'))
    assert current['status'] == 'POINTER_ACTUAL_WBV2_APPLICATION_KEPT_AFTER_LONGRUN'
    measurement = json.loads((Y / 'evidence/wbfix_actual_v2/longrun_35min_after_transport_gap/result.json').read_text())
    assert measurement['completed_requested_window'] and measurement['actual_seconds'] >= 2100
    staged = set(filter(None, git('diff', '--cached', '--name-only', '-z').decode().split('\0')))
    names = ['CURRENT_CAMERA.json', 'PENDING_TASKS.md', 'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md',
        'PENDING_FIELD_TESTS.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json',
        'tools/publish_application_longrun_failure_v1.py', 'tools/publish_wbfix_failure_v1.py',
        'tools/publish_wbfix_v2_progress.py', 'tools/publish_wbfix_v2_kept_v1.py', 'projects/twb_feature_integration_20261023/README.md',
        'projects/twb_feature_integration_20261023/BOARD_VIDEO_REPORT.md',
        'projects/twb_feature_integration_20261023/evidence/application_actual_v3/LIVE_CONTROL.md',
        'skills/anlogic-td-demo-reuse/references/hft2-live-integration.md']
    files = {Path(__file__), *(R / name for name in names)}
    roots = [Y / 'tools', Y / 'handoff/failed_cleanup_recovery_v1', Y / 'handoff/failed_cleanup_recovery_v2']
    roots += [Y / 'evidence' / name for name in ('application_actual_v3', 'wbfix_actual_v1',
        'wbfix_actual_v2', 'wbfix_failure_audit_v1', 'longrun_observer_v1', 'longrun_observer_v2', 'overnight_capacity_v1')]
    omit = {'.vvp', '.ppm', '.exe', '.bit', '.db', '.lic', '.env', '.pyc', '.so', '.dll', '.o', '.a',
        '.zip', '.rknn', '.onnx', '.pt', '.pth', '.tflite', '.sdf', '.ko', '.tar', '.gz', '.xz', '.zst', '.rgb', '.xwd', '.u16le'}
    omitted, raw = [], []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.suffix in omit or '__pycache__' in path.parts:
                continue
            if root.name == 'overnight_capacity_v1' and path.suffix not in ('.json', '.md', '.py', '.log', '.stderr', '.stdout', '.sh'):
                continue
            if path.suffix == '.bin' and path.name != 'first_error_full_body.bin':
                continue
            if re.fullmatch(r'\d{3}\.json', path.name):
                raw.append(dict(path=path.relative_to(R).as_posix(), size=path.stat().st_size, sha256=sha(path)))
                siblings = sorted(path.parent.glob('[0-9][0-9][0-9].json'))
                if path not in siblings[:1] + siblings[-1:]:
                    continue
            if path.stat().st_size >= 8_000_000:
                omitted.append(dict(path=path.relative_to(R).as_posix(), size=path.stat().st_size, sha256=sha(path)))
                continue
            files.add(path)
    progress = json.loads((R / 'GOAL_PROGRESS.json').read_text(encoding='utf8'))
    ledger = Path(progress['full_task_ledger']['path'])
    assert sha(ledger) == progress['full_task_ledger']['sha256']
    revision = json.loads(ledger.read_text())['revision']
    assert revision >= 266
    for number in range(263, revision + 1):
        folder = ledger.parent.parent / f'goal_task_ledger_v{number}'
        if folder.exists():
            files.update(p for p in folder.iterdir() if p.is_file() and p.stat().st_size < 8_000_000)
    O.mkdir()
    snapshot = O / 'GOAL_PROGRESS_snapshot.json'
    snapshot.write_bytes((R / 'GOAL_PROGRESS.json').read_bytes())
    files.add(snapshot)
    save(O / 'raw_snapshot_index.json', dict(status='RAW_LOCAL_BODIES_PRESERVED_AND_HASH_INDEXED', files=raw))
    files.add(O / 'raw_snapshot_index.json')
    paths = {p.relative_to(R).as_posix() for p in files}
    assert not staged & paths and all(p.exists() for p in files)
    rows = [dict(path=p.relative_to(R).as_posix(), size=p.stat().st_size, sha256=sha(p)) for p in sorted(files)]
    save(O / 'files.json', dict(status='WBV2_OWNED_SOURCE_ACTUAL_FAILURE_RECOVERY_AND_LONGRUN_CHECKPOINT', files=rows,
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), omitted_large_files=omitted,
        scope='Owned Y sources/evidence, task views and one skill reference. Other-chat P changes, shared SKILL edits, credentials, models, CAD binaries and archives are excluded.',
        acceptance='Actual non-EOP source repair, byte checks and same-generation35min pass. Human optical/twin/calibration/gesture/game tests remain open. No full goal completion.', full_goal_complete=False))
    rows.append(dict(path=(O / 'files.json').relative_to(R).as_posix(), size=(O / 'files.json').stat().st_size, sha256=sha(O / 'files.json')))
    selected = [row['path'] for row in rows]
    pathfile = O / 'paths.nul'
    pathfile.write_bytes(b'\0'.join(p.encode() for p in selected) + b'\0')
    git('add', '--force', '--pathspec-from-file=' + str(pathfile), '--pathspec-file-nul')
    raw_blobs = git('cat-file', '--batch', input=b''.join((':' + p + '\n').encode() for p in selected))
    pos = 0
    for row in rows:
        end = raw_blobs.index(b'\n', pos)
        header = raw_blobs[pos:end].split()
        assert header[1] == b'blob'
        size = int(header[2]); pos = end + 1
        body = raw_blobs[pos:pos + size]; pos += size
        assert raw_blobs[pos:pos + 1] == b'\n'; pos += 1
        assert size == row['size'] and hashlib.sha256(body).hexdigest() == row['sha256'] and sha(R / row['path']) == row['sha256'], row['path']
    assert pos == len(raw_blobs)
    result = subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'user.name=Codex', '-c', 'user.email=codex@local.invalid',
        'commit', '--only', '--pathspec-from-file=' + str(pathfile), '--pathspec-file-nul',
        '-m', 'Validate non-EOP DMA recovery and retained HFT2 runtime',
        '-m', 'Preserve failed cleanup and observer counterexamples, actual private-driver byte checks and same-generation longrun. Keep human and full project acceptance open.'], cwd=R, capture_output=True)
    (O / 'commit.stdout').write_bytes(result.stdout)
    (O / 'commit.stderr').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    commit = git('rev-parse', 'HEAD').decode().strip()
    changed = set(filter(None, git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit).decode().split('\0')))
    assert changed <= set(selected)
    after = set(filter(None, git('diff', '--cached', '--name-only', '-z').decode().split('\0')))
    assert staged <= after
    value = dict(status='OWNED_WBV2_CHECKPOINT_COMMITTED', commit=commit, files=len(selected), changed_files=len(changed), previous_staged_paths_preserved=sorted(staged), full_goal_complete=False)
    save(O / 'commit_verification.json', value)
    print(json.dumps(value))


if __name__ == '__main__':
    main()
