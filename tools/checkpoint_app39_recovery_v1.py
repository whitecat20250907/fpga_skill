"""Save only owned app39 sources and frozen evidence after original keep."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

R = Path(__file__).resolve().parents[1]
Y = R / 'projects/twb_feature_integration_20261023'
O = Y / 'evidence/app39_recovery_checkpoint_v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def git(*args, **kwargs):
    return subprocess.run(['git', '-c', 'core.autocrlf=false', *args], cwd=R,
        capture_output=True, check=True, **kwargs).stdout


def main():
    assert not O.exists()
    current = json.loads((R / 'CURRENT_CAMERA.json').read_text(encoding='utf8'))
    assert current['status'] == 'POINTER_ACTUAL_APP39_HFT2_GAME_V11_KEPT_AFTER_LONGRUN'
    assert sha(current['selection']['path']) == current['selection']['sha256']
    measurement = json.loads((Y / 'evidence/application_recovery_actual_v4/longrun_35min_v3/result.json').read_text())
    assert measurement['completed_requested_window'] and measurement['actual_seconds'] >= 2100
    staged = set(filter(None, git('diff', '--cached', '--name-only', '-z').decode().split('\0')))
    names = ['CURRENT_CAMERA.json', 'PENDING_TASKS.md', 'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md',
        'PENDING_FIELD_TESTS.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json',
        'tools/publish_app39_recovery_v1.py', 'tools/publish_app39_recovery_v1.README.md',
        'tools/publish_app39_recovery_v2.py', 'tools/publish_app39_recovery_v3.py',
        'tools/publish_app39_recovery_v3.README.md',
        'tools/publish_game_v11_supplemental_v1.py',
        'projects/twb_feature_integration_20261023/README.md',
        'projects/twb_feature_integration_20261023/BOARD_VIDEO_REPORT.md',
        'skills/anlogic-td-demo-reuse/references/hft2-live-integration.md']
    files = {Path(__file__), *(R / name for name in names)}
    roots = [Y / name for name in ('handoff/failed_cleanup_recovery_v3', 'human_metrics_v1',
        'ui_health_persistence_v1', 'convolution_on_verified_baseline_v1')]
    roots += [Y / 'evidence' / name for name in ('application_recovery_actual_v4',
        'sourceonly_target_install_v1', 'longrun_observer_v3', 'c2h1_packet_static_audit_v1',
        'c2h1_packet_fault_reproduction_v1', 'c2h1_bundle_metadata_fault_v1')]
    files.update(Y / 'tools' / name for name in ('execute_application_recovery_actual_v4.py',
        'stage_sourceonly_target_v1.py', 'test_longrun_atomic_health_v3.py', 'watch_application_longrun_v3.py'))
    omit = {'.vvp', '.ppm', '.exe', '.bit', '.db', '.lic', '.env', '.pyc', '.so', '.dll', '.o', '.a',
        '.zip', '.rknn', '.mnn', '.task', '.onnx', '.pt', '.pth', '.tflite', '.sdf', '.ko',
        '.tar', '.gz', '.xz', '.zst', '.rgb', '.xwd', '.u16le', '.bin', '.hex'}
    omitted, raw = [], []
    for root in roots:
        assert root.is_dir(), root
        for path in sorted(root.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            if path.suffix in omit or path.stat().st_size >= 8_000_000:
                omitted.append(dict(path=path.relative_to(R).as_posix(), size=path.stat().st_size, sha256=sha(path)))
                continue
            if re.fullmatch(r'\d{3}\.json', path.name):
                raw.append(dict(path=path.relative_to(R).as_posix(), size=path.stat().st_size, sha256=sha(path)))
                siblings = sorted(path.parent.glob('[0-9][0-9][0-9].json'))
                if path not in siblings[:1] + siblings[-1:]:
                    continue
            files.add(path)
    progress = json.loads((R / 'GOAL_PROGRESS.json').read_text(encoding='utf8'))
    ledger = Path(progress['full_task_ledger']['path'])
    assert sha(ledger) == progress['full_task_ledger']['sha256']
    revision = json.loads(ledger.read_text())['revision']
    assert revision >= 269
    for number in range(267, revision + 1):
        folder = ledger.parent.parent / f'goal_task_ledger_v{number}'
        assert folder.is_dir()
        files.update(p for p in folder.iterdir() if p.is_file() and p.stat().st_size < 8_000_000)
    O.mkdir()
    snapshot = O / 'GOAL_PROGRESS_snapshot.json'
    snapshot.write_bytes((R / 'GOAL_PROGRESS.json').read_bytes())
    files.add(snapshot)
    save(O / 'raw_snapshot_index.json', dict(status='LOCAL_RAW_BODIES_PRESERVED_AND_HASH_INDEXED', files=raw))
    files.add(O / 'raw_snapshot_index.json')
    paths = {p.relative_to(R).as_posix() for p in files}
    assert not staged & paths and all(p.exists() for p in files)
    assert not any(path.startswith('projects/model_image_ops_board_20261023/') for path in paths)
    rows = [dict(path=p.relative_to(R).as_posix(), size=p.stat().st_size, sha256=sha(p)) for p in sorted(files)]
    save(O / 'files.json', dict(status='APP39_OWNED_SOURCE_AND_ACTUAL_RECOVERY_CHECKPOINT', files=rows,
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), omitted_local_artifacts=omitted,
        scope='Owned source and frozen receipts only. Excludes current RTL candidate edits, other-chat P, shared SKILL/user edits, credentials, weights, CAD binaries and archives.',
        acceptance='Exact app39 startup, byte checks, bounded empty-scene metrics, completed35-minute observation and original keep. Old5h51m failure preserved; no DMA root-cause, human, optical, full FPGA candidate or full-goal acceptance.', full_goal_complete=False))
    files_json = O / 'files.json'
    rows.append(dict(path=files_json.relative_to(R).as_posix(), size=files_json.stat().st_size, sha256=sha(files_json)))
    selected = [row['path'] for row in rows]
    pathfile = O / 'paths.nul'
    pathfile.write_bytes(b'\0'.join(path.encode() for path in selected) + b'\0')
    git('add', '--force', '--pathspec-from-file=' + str(pathfile), '--pathspec-file-nul')
    blobs = git('cat-file', '--batch', input=b''.join((':' + path + '\n').encode() for path in selected))
    pos = 0
    for row in rows:
        end = blobs.index(b'\n', pos)
        header = blobs[pos:end].split()
        assert header[1] == b'blob'
        size = int(header[2]); pos = end + 1
        body = blobs[pos:pos + size]; pos += size
        assert blobs[pos:pos + 1] == b'\n'; pos += 1
        assert size == row['size'] and hashlib.sha256(body).hexdigest() == row['sha256'] and sha(R / row['path']) == row['sha256'], row['path']
    assert pos == len(blobs)
    process = subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'user.name=Codex', '-c', 'user.email=codex@local.invalid',
        'commit', '--only', '--pathspec-from-file=' + str(pathfile), '--pathspec-file-nul',
        '-m', 'Keep source-bound app39 recovery and bounded board observations',
        '-m', 'Record actual byte checks, empty-scene metrics, original keep, v11 supplemental game acceptance and independent FPGA fault reproductions. Preserve prior terminal failure and untested human/root-cause boundaries.'], cwd=R, capture_output=True)
    (O / 'commit.stdout').write_bytes(process.stdout)
    (O / 'commit.stderr').write_bytes(process.stderr)
    assert process.returncode == 0, process.stderr.decode(errors='replace')
    commit = git('rev-parse', 'HEAD').decode().strip()
    changed = set(filter(None, git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit).decode().split('\0')))
    assert changed <= set(selected)
    after = set(filter(None, git('diff', '--cached', '--name-only', '-z').decode().split('\0')))
    assert staged <= after
    result = dict(status='OWNED_APP39_RECOVERY_COMMITTED', commit=commit, files=len(selected), changed_files=len(changed), previous_staged_paths_preserved=sorted(staged), full_goal_complete=False)
    save(O / 'commit_verification.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
