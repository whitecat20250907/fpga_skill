#!/usr/bin/env python3
"""Root-owned, explicit isolated TD invocation; never imports an old default DB.

Exit 0 means a nonempty report was generated and still requires CDC review.
Exit 2 means unresolved/error/crash/UNDEFINED; no CDC/MTBF PASS is fabricated.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def checked_file(text, expected_hash=None):
    path = Path(text).resolve(strict=True)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f'Not a nonempty file: {path}')
    actual = sha256(path)
    if expected_hash is not None:
        if not re.fullmatch(r'[0-9a-fA-F]{64}', expected_hash):
            raise ValueError('Expected SHA-256 must be 64 hexadecimal digits')
        if actual != expected_hash.lower():
            raise ValueError(f'Hash disagreement for {path}: {actual}')
    return path, actual


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--td', default='E:/qianrufpga/TD/bin/td_commands_prompt.exe')
    ap.add_argument('--checkpoint', required=True)
    ap.add_argument('--checkpoint-sha256', required=True)
    ap.add_argument('--checkpoint-stage', required=True, choices=('place', 'pr'))
    ap.add_argument('--qualified-bit', required=True)
    ap.add_argument('--bit-sha256', required=True)
    ap.add_argument('--timing-status', required=True, help='CURRENT same-build final .ts, SWNS/HWNS >= 0')
    ap.add_argument('--build-id', required=True, help='Root-confirmed current build ID, e.g. build07_direct')
    ap.add_argument('--out', required=True, help='A nonexistent fresh diagnostic directory')
    ap.add_argument('--timeout-seconds', type=int, default=300)
    args = ap.parse_args()
    out = Path(args.out).resolve()
    try:
        if out.exists():
            raise ValueError(f'Refusing to overwrite existing evidence: {out}')
        if args.timeout_seconds <= 0 or not re.fullmatch(r'[A-Za-z0-9_.-]+', args.build_id):
            raise ValueError('Invalid timeout/build ID')
        td, td_hash = checked_file(args.td)
        checkpoint, checkpoint_hash = checked_file(args.checkpoint, args.checkpoint_sha256)
        bit, bit_hash = checked_file(args.qualified_bit, args.bit_sha256)
        timing, timing_hash = checked_file(args.timing_status)
        if not (checkpoint.parent == bit.parent == timing.parent):
            raise ValueError('Checkpoint, qualified bit and final timing must belong to the SAME fresh build directory')
        suffix = '_' + args.checkpoint_stage + '.db'
        if not checkpoint.name.endswith(suffix):
            raise ValueError(f'Checkpoint must end with {suffix}')
        design_stem = checkpoint.name[:-len(suffix)]
        if bit.name not in (design_stem + '.bit', design_stem + '_compress.bit'):
            raise ValueError('Bit filename does not match checkpoint design')
        if timing.name != design_stem + '_phy.ts':
            raise ValueError('Final timing filename does not match checkpoint design')
        text = timing.read_text(encoding='utf-8', errors='replace')
        slacks = {}
        for key in ('SWNS', 'HWNS'):
            found = re.search(r'\b' + key + r':\s*([-+0-9.]+)ns\b', text)
            if not found or float(found.group(1)) < 0:
                raise ValueError(f'{key} is missing or negative; this is not a qualified current checkpoint')
            slacks[key + '_ns'] = float(found.group(1))
        script, script_hash = checked_file(Path(__file__).with_name('report_mtbf_isolated.tcl'))
        helper, helper_hash = checked_file(script.with_name('cdc_attribute_audit.tcl'))
    except (ValueError, OSError) as e:
        print(f'ISOLATED_MTBF_INPUT_REJECTED: {e}', file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=False)
    protected = {'checkpoint': (checkpoint, checkpoint_hash), 'qualified_bit': (bit, bit_hash),
                 'timing_status': (timing, timing_hash)}
    manifest = {
        'status': 'NOT_RUN', 'cdc_acceptance': 'UNRESOLVED', 'build_id': args.build_id,
        'stage': args.checkpoint_stage, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'inputs': {key: {'path': str(p), 'sha256': h} for key, (p, h) in protected.items()},
        'td': {'path': str(td), 'sha256': td_hash},
        'scripts': {'tcl_sha256': script_hash, 'audit_helper_sha256': helper_hash},
        'final_timing': slacks, 'command': [td.as_posix(), script.as_posix()],
        'scope': 'Read-only isolated import/report. No synth/place/route/bitgen; original placement directives and CDC coverage still require review.',
    }
    manifest_path = out / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    env = os.environ.copy()
    # This TD CLI evaluates the script argument as Tcl text: Windows backslash
    # paths become escape sequences (\t/\r/\f). Always pass forward slashes.
    env.update(MTBF_CHECKPOINT=checkpoint.as_posix(), MTBF_OUTPUT=out.as_posix(),
               MTBF_CHECKPOINT_STAGE=args.checkpoint_stage, MTBF_BUILD_ID=args.build_id)
    try:
        with (out / 'td.stdout.log').open('wb') as log:
            # The script is the SOLE positional argument. -tcl is unsupported
            # by this installed TD CLI. Root's current TD build is not touched.
            result = subprocess.run([td.as_posix(), script.as_posix()], cwd=out, env=env,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    timeout=args.timeout_seconds, check=False)
        manifest['process_returncode'] = result.returncode
        log_text = (out / 'td.stdout.log').read_text(encoding='utf-8', errors='replace')
        stage_path = out / 'stage.txt'
        manifest['last_stage'] = stage_path.read_text().strip() if stage_path.exists() else None
        report = out / 'mtbf.rpt'
        if report.exists() and report.stat().st_size:
            report_text = report.read_text(encoding='utf-8', errors='replace')
            manifest['report'] = {'path': str(report), 'sha256': sha256(report), 'bytes': report.stat().st_size}
            manifest['undefined_present'] = bool(re.search(r'\bUNDEFINED\b', report_text, re.I))
        else:
            manifest['undefined_present'] = None
        completed = (result.returncode == 0 and manifest['last_stage'] == 'complete_report_requires_review'
                     and 'ISOLATED_MTBF_REPORT_GENERATED_REQUIRES_REVIEW' in log_text
                     and 'report' in manifest)
        if completed and not manifest['undefined_present']:
            manifest['status'] = 'REPORT_GENERATED_REQUIRES_REVIEW'
        elif completed:
            manifest['status'] = 'UNRESOLVED_UNDEFINED_IN_REAL_REPORT'
        else:
            manifest['status'] = 'UNRESOLVED_TD_ERROR_OR_NATIVE_CRASH_OR_NO_REPORT'
    except subprocess.TimeoutExpired:
        manifest['status'] = 'UNRESOLVED_ISOLATED_PROCESS_TIMEOUT'
    except OSError as e:
        manifest['status'] = 'UNRESOLVED_LAUNCH_ERROR'
        manifest['error'] = str(e)
    finally:
        manifest['protected_inputs_unchanged'] = {}
        for key, (path, initial) in protected.items():
            try:
                current = sha256(path)
                manifest['protected_inputs_unchanged'][key] = current == initial
                manifest['inputs'][key]['after_sha256'] = current
            except OSError as e:
                manifest['protected_inputs_unchanged'][key] = False
                manifest['inputs'][key]['after_error'] = str(e)
        if not all(manifest['protected_inputs_unchanged'].values()):
            manifest['status'] = 'UNRESOLVED_PROTECTED_INPUT_CHANGED'
        manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': manifest['status'], 'cdc_acceptance': 'UNRESOLVED', 'manifest': str(manifest_path)}))
    return 0 if manifest['status'] == 'REPORT_GENERATED_REQUIRES_REVIEW' else 2


if __name__ == '__main__':
    sys.exit(main())
