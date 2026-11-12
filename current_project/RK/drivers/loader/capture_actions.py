"""Remote actions for the owned ISP50 SRAM transaction; import has no side effects.

The Windows runner embeds this source and calls dispatch(action, pinned_config).
Never run independently: candidate identity comes from the owned JTAG log.
Stage changes occur only with no native owner/FD and ISP8 reg_enable==0.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import struct
import subprocess
import sys
import tarfile
import time
import traceback

B = Path('/userdata/gaze_model_migration_v1_20261014')
APP = B / 'app_v24'
BASE = Path('/home/linaro/pcie_fix_20261003')
DEPLOY = Path('/home/linaro/pcie_fix_20261003/sgdma_wb_trial_20261024_v2/loader')
ISP = B / 'ISP_probe_helper_v1/isp_probe_mmio'
LINEAR = BASE / 'linear_mmio47_stage_v1/linear_gate_mmio'
ROOT = Path('/sys/bus/platform/devices/2a210000.pcie')
STAGES = (1, 2, 3, 4, 5, 6, 7, 0)


def require(ok, detail):
    if not ok:
        raise RuntimeError(detail)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.replace(path)


def owners():
    model, capture = [], []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / 'cmdline').read_bytes()
            cwd = (p / 'cwd').resolve()
            # Track the live process instance, not just a recyclable PID.
            start = int((p / 'stat').read_text().rsplit(')', 1)[1].split()[19])
            row = dict(pid=int(p.name), start_ticks=start, cwd=str(cwd))
            if b'\0run_gaze.py\0' in cmd:
                require(cwd == APP, 'Unexpected model application owner')
                model.append(row)
            if cmd.startswith(str(APP / 'capture_native').encode() + b'\0'):
                require(cwd == APP, 'Unexpected capture cwd')
                capture.append(row)
        except (OSError, ProcessLookupError):
            pass
    return dict(model=model, capture=capture)


def video_device():
    nodes = [p.parent.name for p in Path('/sys/class/video4linux').glob('video*/name')
             if p.read_text().strip() == 'Milianke PCIe Capture']
    require(len(nodes) == 1, 'Expected exactly one Milianke PCIe Capture')
    return '/dev/' + nodes[0]


def camera_fds(allowed=None):
    rows = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            fds = list((p / 'fd').iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if re.fullmatch('/dev/video[0-9]+', target):
                require(allowed is not None and target == allowed, 'Unexpected/open camera FD: ' + target)
                rows.append(dict(pid=int(p.name), fd=fd.name, target=target))
    return rows


def environment(cfg):
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == cfg['boot_id'], 'Board boot changed')
    require(Path('/sys/firmware/devicetree/base/usb@23400000/status').read_bytes().rstrip(b'\0') == b'disabled', 'USB1 must remain disabled')
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            command = (p / 'cmdline').read_bytes().split(b'\0')[0].decode(errors='replace')
        except OSError:
            continue
        require(not re.fullmatch(r'(?:rkaiq\w*|camera_engine\w*|rkisp_demo\w*)', Path(command).name, re.I), 'Real AIQ/RK CSI process present')


def verify_files(cfg):
    for path, digest in cfg['remote_files'].items():
        require(sha(path) == digest, 'Pinned remote file changed: ' + path)


def mmio(helper, value=None):
    args = [str(helper)] + ([] if value is None else [str(value)])
    return json.loads(subprocess.check_output(args, text=True, timeout=5))


def full_hist(row):
    return (row.get('shadow') == row.get('active') == row.get('previous_hist_gate') == 0
            and row.get('histogram_stable') and row.get('histogram_complete')
            and row.get('histogram_pixels') == 2073600)


def kernel_faults(raw):
    # A word/line boundary prevents normal "ramoops:" initialization from
    # matching "Oops:". A real Oops on the same line remains a fault candidate.
    return [x for x in raw.splitlines() if re.search(
        r'(?:^|\s)Oops:|Internal error:|Unable to handle kernel|iommu.*(?:page fault|fault addr)|rkisp.*timeout|Out of memory:|Killed process|oom-kill:', x, re.I)]


def kernel_snapshot():
    raw = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager', '-o', 'cat'], text=True, timeout=8)
    faults = kernel_faults(raw)
    require(not faults, 'Current boot kernel fault candidates: ' + repr(faults))
    return dict(sha256=hashlib.sha256(raw.encode()).hexdigest(), lines=len(raw.splitlines()), faults=faults)


def runtime(cfg, require_new=False, before=None):
    environment(cfg)
    own = owners()
    require(len(own['model']) == len(own['capture']) == 1, 'Exactly one model and native capture required')
    if require_new:
        require(own['model'][0] not in before['owners']['model'], 'Old model instance did not exit')
        require(own['capture'][0] not in before['owners']['capture'], 'Old native instance did not exit')
    fd_rows = camera_fds(video_device())
    require(fd_rows and {r['pid'] for r in fd_rows} == {own['capture'][0]['pid']}, 'Camera FD not exclusively owned by native')
    roots = set()
    for f in (Path('/proc') / str(own['model'][0]['pid']) / 'fd').iterdir():
        try:
            p = Path(os.readlink(f))
        except OSError:
            continue
        if p.name == 'gaze.csv' and p.parent.parent == B / 'gaze_sessions':
            roots.add(p.parent)
    require(len(roots) == 1, 'Model session must come from actual open gaze.csv FD')
    session = roots.pop()
    if require_new:
        require(str(session) != before['session'], 'Old model session reused')
    meta = json.loads((session / 'session.json').read_text())
    require(meta['backend'] == 'RK3576_NPU_RKNNLite', 'Original NPU backend required')
    require(meta['settings']['face_cpu_threads'] == 4 and meta['settings']['overlap_inference'] is True, 'Selected CPU4/overlap changed')
    model = Path(meta['model']['path'])
    require(model.is_relative_to(APP) and sha(model) == cfg['model_sha256'], 'Original selected model changed')
    status = json.loads((B / 'control_status.json').read_text())
    require(0 <= time.time() - status['time'] < 2 and 0 <= status['age_ms'] < 500 and not status['mouse_enabled'], 'Control status stale or mouse enabled')
    old_time = status['time']
    time.sleep(.15)
    status = json.loads((B / 'control_status.json').read_text())
    require(status['time'] > old_time and 0 <= time.time() - status['time'] < 2, 'Control heartbeat not advancing')
    gate = mmio(LINEAR)
    require(full_hist(gate), 'Selected gate0/full histogram not restored')
    pci = Path('/sys/bus/pci/devices/0000:21:00.0')
    speed, width = (pci / 'current_link_speed').read_text().strip(), (pci / 'current_link_width').read_text().strip()
    require(speed.startswith('5.0') and width == '1', 'PCIe must be 5GT/s x1')
    return dict(owners=own, session=str(session), metadata=meta, control=status, gate=gate,
                boot_id=cfg['boot_id'], PCIe_speed=speed, PCIe_width=width, kernel=kernel_snapshot())


def preflight(cfg, out):
    verify_files(cfg)
    environment(cfg)
    require(__import__('shutil').disk_usage('/home/linaro').free > 536870912, 'Insufficient capture disk space')
    row = runtime(cfg)
    write_json(out / 'before.json', row)
    return row


def stop(cfg, out):
    verify_files(cfg)
    environment(cfg)
    # User-authorized global F10 clean shutdown, using selected app24 API.
    sys.path.insert(0, str(APP))
    from desktop_input import X11Input, display_geometry
    os.environ.update(DISPLAY=':0', XAUTHORITY='/home/linaro/.Xauthority')
    x = X11Input(display_geometry())
    try:
        key = x.x.XKeysymToKeycode(x.display, 0xffc7)
        require(bool(key), 'F10 key unavailable')
        f = x.xt.XTestFakeKeyEvent
        f.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
        f.restype = C.c_int
        require(bool(f(x.display, key, 1, 0)), 'F10 key-down failed')
        x.x.XFlush(x.display)
        time.sleep(.1)
        require(bool(f(x.display, key, 0, 0)), 'F10 key-up failed')
        x.x.XFlush(x.display)
    finally:
        x.close()
    for _ in range(60):
        own = owners()
        if not own['model'] and not own['capture']:
            camera_fds()
            write_json(out / 'stopped.json', dict(clean_F10=True, owners=own))
            return dict(clean_F10=True)
        time.sleep(.2)
    raise RuntimeError('Model/native did not exit cleanly; no forced kill')


def quiesce(cfg, out):
    environment(cfg)
    own = owners()
    require(not own['model'] and not own['capture'], 'Stop model/native before PCIe quiesce')
    camera_fds()
    devices = list(Path('/sys/bus/pci/devices').iterdir())
    require(all(p.name in ('0000:20:00.0', '0000:21:00.0') for p in devices), 'Unexpected PCIe topology')
    for mod in ('milianke_v4l2', 'anlogic_pci'):
        if (Path('/sys/module') / mod).exists():
            subprocess.run(['rmmod', mod], check=True, timeout=8)
    if (ROOT / 'driver').exists():
        Path('/sys/bus/platform/drivers/rk-pcie/unbind').write_text('2a210000.pcie\n')
    require(not list(Path('/sys/bus/pci/devices').iterdir()) and not (ROOT / 'driver').exists(), 'Root/DMA not quiesced')
    return dict(PCIe_root_unbound=True, DMA_modules_unloaded=True)


def reprobe(cfg, out):
    environment(cfg)
    verify_files(cfg)
    subprocess.run(['bash', str(DEPLOY / 'pcie_setup.sh')], check=True, timeout=20)
    return dict(device=video_device())


def record(reader, deadline):
    """Bounded exact MCF1 reader; no buffered read can hide a hung child."""
    def exact(size):
        buf = bytearray()
        sel = selectors.DefaultSelector()
        sel.register(reader, selectors.EVENT_READ)
        try:
            while len(buf) < size:
                left = deadline - time.monotonic()
                require(left > 0, 'Native MCF1 deadline expired')
                require(bool(sel.select(min(left, .5))) or time.monotonic() < deadline, 'Native MCF1 timeout')
                # Read only after readiness; a pipe read may return partial bytes.
                if not sel.select(0):
                    continue
                chunk = os.read(reader.fileno(), min(size - len(buf), 1048576))
                require(bool(chunk), 'Incomplete native MCF1 record')
                buf.extend(chunk)
        finally:
            sel.close()
        return bytes(buf)
    magic, njson, size = struct.unpack('<4sII', exact(12))
    require(magic == b'MCF1' and 0 < njson <= 65536 and size <= 6220800, 'Invalid MCF1 envelope')
    return json.loads(exact(njson)), exact(size)


def validate_payload(data, stage, width=1920, height=1080):
    require(len(data) == width * height * 3, 'Incomplete/full-size RGB3 required')
    import numpy as np
    rgb = np.frombuffer(data, np.uint8).reshape(height, width, 3)
    if stage in (1, 2):
        require(bool(np.all(rgb[:, :, 1] < 4)), 'RAW10 upper six G bits are nonzero')
        marker = (0xa0 if stage == 1 else 0xb0) + np.arange(width, dtype=np.uint8) % 4
        require(bool(np.all(rgb[:, :, 2] == marker[None, :])), 'RAW stage/lane markers incorrect')
        raw = rgb[:, :, 0].astype(np.uint16) | (rgb[:, :, 1].astype(np.uint16) << 8)
        return dict(RAW10_min=int(raw.min()), RAW10_max=int(raw.max()), RAW10_mean=float(raw.mean()),
                    parity_means=[[float(raw[y::2, x::2].mean()) for x in range(2)] for y in range(2)])
    return dict(RGB_mean=[float(v) for v in rgb.mean((0, 1))])


def validate_start(meta, data, pid):
    require(meta['kind'] == 'start' and not data and meta['pid'] == pid
            and meta['hardware_capture'] is True and meta['width'] == 1920 and meta['height'] == 1080
            and meta['fourcc'] == 'RGB3' and meta['type'] == 1
            and meta['driver'] == 'milianke-v4l2' and meta['bus_info'] == 'PCI:0000:21:00.0'
            and meta['planes'] == [dict(stride=5760, sizeimage=6220800)] and 2 <= meta['buffers'] <= 16
            and meta['output_policy'] == 'bounded_latest_copy' and meta['copy_slots'] == 2
            and meta['output_stall_timeout_ms'] == 2000
            and 'output_transform' not in meta, 'Exact selected native full RGB3 start contract required')


def validate_frame(meta, data, start, previous):
    require(meta['kind'] == 'frame' and len(data) == 6220800
            and isinstance(meta['flags'], int) and not meta['flags'] & 0x40
            and meta['flags'] & 0xe000 == 0x2000  # V4L2 timestamp MONOTONIC
            and meta['field'] == 1  # V4L2_FIELD_NONE in the pinned driver
            and 0 <= meta['index'] < start['buffers']
            and meta['planes'] == [dict(bytesused=6220800, data_offset=0, payload=6220800)]
            and 0 < meta['timestamp_ns'] <= meta['dequeue_ns'] and meta['sequence'] >= 0,
            'Invalid/error/full-size RGB3 frame metadata')
    if previous:
        require(meta['sequence'] > previous['sequence'] and meta['timestamp_ns'] > previous['timestamp_ns']
                and meta['dequeue_ns'] > previous['dequeue_ns'], 'Nonmonotonic sequence/timestamp/dequeue clock')


def validate_end(meta, data, frames, seconds):
    require(meta['kind'] == 'end' and not data and meta['errno'] == meta['cleanup_errno'] == 0
            and meta['frames'] == frames and meta['stage'] == 'duration_complete'
            and meta['captured_frames'] == frames + meta['software_dropped_frames']
            and meta['software_dropped_frames'] >= 0 and meta['elapsed_ns'] >= seconds * 1000000000,
            'Native end/cleanup/captured/dropped/duration counters failed')


def validate_eof(data):
    require(data == b'', 'Trailing bytes/records after native end')


def cleanup_tail_summary(blob):
    """Describe drained cleanup bytes; partial framing is preserved, never a PASS."""
    position, records, end = 0, 0, None
    try:
        while position < len(blob):
            require(len(blob) - position >= 12, 'Partial cleanup MCF1 header')
            magic, njson, size = struct.unpack_from('<4sII', blob, position)
            position += 12
            require(magic == b'MCF1' and 0 < njson <= 65536 and size <= 6220800
                    and len(blob) - position >= njson + size, 'Partial/invalid cleanup MCF1 record')
            meta = json.loads(blob[position:position + njson])
            position += njson + size
            records += 1
            if meta['kind'] == 'end':
                require(size == 0 and position == len(blob), 'Cleanup end has payload/trailing bytes')
                end = meta
        return dict(records=records, end=end, complete_framing=True)
    except (RuntimeError, ValueError, KeyError) as error:
        return dict(records=records, end=end, complete_framing=False, parse_error=repr(error))


def sample_plan(stage, qualified_hist_index, buffers):
    if stage in (1, 2, 3):
        return dict(indices=[12, 20], discard_after_gate0_hist=None,
                    scope='RAW/demosaic taps bypass CCM; histogram attribution is inapplicable')
    require(qualified_hist_index is not None, 'Gate0 full histogram qualification required before planning RGB saves')
    # Drain at least eight subsequent received frames; use the larger negotiated
    # DMA-buffer bound plus two native slots and one pipe frame where necessary.
    discard = max(8, buffers + 3)
    first = qualified_hist_index + discard + 1
    return dict(indices=[first, first + 8], discard_after_gate0_hist=discard,
                scope='Both saves follow full gate0 histogram and bounded queue drain')


def capture_stage(cfg, out, stage):
    require(stage in STAGES, 'Unsupported probe stage')
    own = owners()
    require(not own['model'] and not own['capture'], 'Capture STOP required before each stage change')
    camera_fds()
    before = mmio(ISP)
    require(not before['capture_enabled'], 'reg_enable must be zero before writing stage')
    setting = mmio(ISP, stage)
    require(setting['stage'] == stage and not setting['capture_enabled']
            and setting['rejected_writes'] == before['rejected_writes'], 'Stage write/readback/refusal count mismatch')
    row = dict(stage=stage, configured=setting, frames=[], histogram_required=stage not in (1, 2, 3), saved=[],
               sample_plan=sample_plan(stage, None, 0) if stage in (1, 2, 3) else None)
    seconds = cfg['capture_seconds_per_stage']
    deadline = time.monotonic() + seconds + 8
    child = None
    hist = None
    try:
        with (out / ('stage%d_native.log' % stage)).open('xb') as log:
            # Full RGB3; deliberately no --rgb-centre3 downsampling.
            child = subprocess.Popen([str(APP / 'capture_native'), video_device(), '1920', '1080', 'RGB3', str(seconds)],
                                     cwd=APP, stdout=subprocess.PIPE, stderr=log, bufsize=0)
            saw_start = False
            while True:
                meta, data = record(child.stdout, deadline)
                if meta['kind'] == 'start':
                    require(not saw_start, 'Duplicate native start')
                    validate_start(meta, data, child.pid)
                    saw_start = True
                    row['start'] = meta
                elif meta['kind'] == 'end':
                    require(saw_start and not data, 'Malformed native end')
                    row['end'] = meta
                    validate_end(meta, data, len(row['frames']), seconds)
                    break
                else:
                    require(saw_start, 'Frame before start')
                    validate_frame(meta, data, row['start'], row['frames'][-1] if row['frames'] else None)
                    number = len(row['frames'])
                    if number == 0:
                        # Native emits start before STREAMON. The first complete
                        # frame is the synchronization point for readback/gate0.
                        active = mmio(ISP)
                        require(active['capture_enabled'] and active['stage'] == stage
                                and active['rejected_writes'] == before['rejected_writes'], 'Probe stage did not survive S_FMT/STREAMON reset')
                        row['after_STREAMON'] = active
                        row['gate0_after_STREAMON'] = mmio(LINEAR, 0)
                    stats = validate_payload(data, stage)
                    row['frames'].append(dict(sequence=meta['sequence'], timestamp_ns=meta['timestamp_ns'], dequeue_ns=meta['dequeue_ns'], **stats))
                    if number >= 3 and row['histogram_required'] and hist is None:
                        candidate = mmio(LINEAR)
                        if full_hist(candidate):
                            hist = candidate
                            row['gate0_hist_qualified_frame_index'] = number
                            row['gate0_hist_qualified'] = candidate
                            row['sample_plan'] = sample_plan(stage, number, row['start']['buffers'])
                    plan = row['sample_plan']
                    if plan is not None and number in plan['indices']:
                        hist_before_save = mmio(LINEAR) if row['histogram_required'] else None
                        if row['histogram_required']:
                            require(full_hist(hist_before_save), 'Gate0 histogram lost before saved RGB frame')
                        name = 'stage%d_frame%d.rgb' % (stage, number)
                        (out / name).write_bytes(data)
                        hist_after_save = mmio(LINEAR) if row['histogram_required'] else None
                        if row['histogram_required']:
                            require(full_hist(hist_after_save), 'Gate0 histogram lost after saved RGB frame')
                        row['saved'].append(dict(path=str(out / name), sha256=hashlib.sha256(data).hexdigest(), metadata=meta,
                                                 received_frame_index=number, histogram_before_save=hist_before_save,
                                                 histogram_after_save=hist_after_save))
            require(child.wait(timeout=5) == 0, 'Native capture terminal failure')
            # Direct child is terminal, so this unbuffered pipe read cannot hang.
            validate_eof(child.stdout.read(1))
            require(len(row['saved']) == 2, 'Insufficient complete frames after required gate0/queue settle; no attributed RGB capture accepted')
            if row['histogram_required']:
                require(hist is not None, 'Stage4..7/0 gate0 full histogram missing')
            row['histogram'] = hist
            row['histogram_scope'] = 'Complete CCM input histogram' if row['histogram_required'] else 'Skipped: RAW/demosaic bypasses CCM, full histogram is inapplicable'
    finally:
        if child is not None:
            row['native_pid'] = child.pid
            row['termination_requested'] = False
            if child.poll() is None:
                # Native persistent handler performs STREAMOFF and returns DMA buffers.
                row['termination_requested'] = True
                child.send_signal(signal.SIGTERM)
                try:
                    tail, _ = child.communicate(timeout=10)
                    row['cleanup_tail'] = cleanup_tail_summary(tail)
                    if tail:
                        path = out / ('stage%d_cleanup_tail.mcf1' % stage)
                        path.write_bytes(tail)
                        row['cleanup_tail_file'] = dict(path=str(path), bytes=len(tail), sha256=sha(path))
                except subprocess.TimeoutExpired as error:
                    row['native_cleanup_timeout'] = True
                    row['native_returncode'] = child.poll()
                    if error.output:
                        path = out / ('stage%d_cleanup_partial.mcf1' % stage)
                        path.write_bytes(error.output)
                        row['cleanup_partial_file'] = dict(path=str(path), bytes=len(error.output), sha256=sha(path))
                    write_json(out / ('stage%d_result.json' % stage), row)
                    raise RuntimeError('Native cleanup did not finish; do not JTAG/rebind until FD and DMA quiescence are proven')
            row['native_returncode'] = child.returncode
            if child.stdout:
                child.stdout.close()
        camera_fds()
        stopped = mmio(ISP)
        require(not stopped['capture_enabled'] and stopped['stage'] == stage
                and stopped['rejected_writes'] == before['rejected_writes'], 'Capture STOP/stage/refusal invariant failed')
        row['after_STOP'] = stopped
        write_json(out / ('stage%d_result.json' % stage), row)
    return row


def capture(cfg, out):
    verify_files(cfg)
    environment(cfg)
    # Warm the numerical runtime before starting the two-second native interval.
    import numpy
    results = []
    try:
        for stage in STAGES:
            results.append(capture_stage(cfg, out, stage))
        return dict(status='CAPTURED_REAL50_RAW10_AND_8_STAGES_NOT_OPTICAL_ACCEPTANCE', stages=results)
    finally:
        # Best effort normal stage before quiesce; never a hot change.
        if not owners()['capture']:
            camera_fds()
            state = mmio(ISP)
            if not state['capture_enabled']:
                mmio(ISP, 0)


def restore(cfg, out):
    verify_files(cfg)
    environment(cfg)
    before = json.loads((out / 'before.json').read_text())
    if not (ROOT / 'driver').exists() or not Path('/sys/module/milianke_v4l2').exists():
        reprobe(cfg, out)
    own = owners()
    if not own['model'] and not own['capture']:
        with (out / 'restored_model.log').open('ab') as log:
            child = subprocess.Popen(['runuser', '-u', 'linaro', '--', 'bash', str(B / 'bin/gaze.sh')],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(out / 'launcher_requested.json', dict(pid=child.pid, actual_owner_discovery_required=True))
    last = None
    for _ in range(120):
        try:
            own = owners()
            if len(own['capture']) == 1:
                # STREAMON resets linear gate; reapply only after actual capture exists.
                mmio(LINEAR, 0)
                row = runtime(cfg, require_new=(out / 'stopped.json').exists(), before=before)
                row['CURRENT_publication_required'] = True
                row['Flash_written'] = False
                write_json(out / 'restored_runtime.json', row)
                return row
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
            last = repr(error)
        time.sleep(.25)
    raise RuntimeError('Restoration not verified: ' + str(last))


def dispatch(action, cfg):
    out = Path(cfg['remote_output'])
    require(out.parent == BASE and re.fullmatch(r'isp50_trial_[0-9A-Za-z_]+', out.name), 'Unsafe remote evidence directory')
    if action == 'preflight':
        require(not out.exists(), 'Remote attempt evidence already exists')
        out.mkdir()
    else:
        require(out.is_dir() and (out / 'before.json').is_file(), 'Missing owned remote preflight')
    funcs = dict(preflight=preflight, stop=stop, quiesce=quiesce, reprobe=reprobe, capture=capture, restore=restore)
    require(action in funcs, 'Unknown remote action')
    try:
        row = funcs[action](cfg, out)
        write_json(out / (action + '.json'), row)
        # Only summaries travel through SSH; complete source data remains in archive.
        print(json.dumps(dict(action=action, ok=True, result=row if action != 'capture' else dict(status=row['status'], stage_count=len(row['stages'])))), flush=True)
        if action == 'restore':
            archive = out.with_suffix('.tar.gz')
            with tarfile.open(archive, 'w:gz') as tar:
                tar.add(out, arcname=out.name)
            print(json.dumps(dict(archive=str(archive), sha256=sha(archive))), flush=True)
    except BaseException as error:
        write_json(out / (action + '_failed.json'), dict(error=repr(error), traceback=traceback.format_exc()))
        raise
