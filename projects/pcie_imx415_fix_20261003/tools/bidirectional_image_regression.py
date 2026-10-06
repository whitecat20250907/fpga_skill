#!/usr/bin/env python3
"""RK-local build07 full-image regression. Never flashes or unbinds hardware.

Host-only: python bidirectional_image_regression.py --self-test
RK: sudo python3 tools/bidirectional_image_regression.py --camera-rgb PATH
Only milianke_v4l2 is temporarily unloaded; anlogic_pci remains loaded.
"""
import argparse
import hashlib
import json
import math
import mmap
import os
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

VERSION = 0x56440701
EXPECTED_PLAN = (("known_720_64K", 1280, 720, 20, 65536),
                 ("known_1080_4K", 1920, 1080, 3, 4096),
                 ("known_1080_64K", 1920, 1080, 20, 65536),
                 ("known_1080_1M", 1920, 1080, 50, 1048576))
REG_OFFSETS = (0x5c, 0x60, 0x20, 0x90, 0xa4)
POLL_ERROR = re.compile(r"(?:poll[^\n]*(?:timeout|timed out)|(?:timeout|timed out)[^\n]*poll)", re.I)


class Failure(RuntimeError):
    pass


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def one_json(text):
    rows = [json.loads(line) for line in text.splitlines() if line.startswith("{")]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise Failure("expected exactly one image_roundtrip JSON result")
    return rows[0]


def distinct(source, echo):
    source, echo = Path(source), Path(echo)
    if source.resolve() == echo.resolve() or (echo.exists() and os.path.samefile(source, echo)):
        raise Failure("source and echo must not be the same inode/path")


def validate_result(row, source, echo, frames, chunk, rc):
    distinct(source, echo)
    size = Path(source).stat().st_size
    expected = {"frames": frames, "frame_bytes": size, "chunk_bytes": chunk,
                "sent": size * frames, "received": size * frames,
                "byte_mismatches": 0, "failed": False, "interrupted": False}
    if rc != 0 or any(row.get(k) != v for k, v in expected.items()):
        raise Failure(f"full image result failed: rc={rc}, result={row}, expected={expected}")
    seconds = row.get("seconds")
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise Failure("image test lacks a finite positive measured duration")
    if Path(echo).stat().st_size != size:
        raise Failure("echo must contain exactly one complete source frame")
    a, b = sha(source), sha(echo)
    if a != b:
        raise Failure("source/echo SHA256 differs")
    return dict(frame_bytes=size, frames=frames, exact_bytes=size * frames,
                byte_mismatches=0, source_sha256=a, echo_sha256=b)


def kernel_delta(before, after):
    # Never silently ignore a wrapped/cleared kernel ring buffer.
    if not after.startswith(before):
        raise Failure("dmesg ring changed/wrapped; cannot prove no residual poll timeout")
    return after[len(before):]


def active_clients(paths, proc=Path("/proc")):
    watched = set()
    for path in paths:
        s = Path(path).stat()
        watched.add((s.st_dev, s.st_ino))
    found = []
    for p in proc.glob("[0-9]*"):
        if int(p.name) == os.getpid():
            continue
        try:
            for fd in (p / "fd").iterdir():
                try:
                    s = fd.stat()
                    if (s.st_dev, s.st_ino) in watched:
                        found.append(dict(pid=int(p.name), fd=fd.name, target=os.readlink(fd)))
                except FileNotFoundError:
                    pass
        except (FileNotFoundError, ProcessLookupError):
            pass
        except PermissionError as e:
            raise Failure(f"cannot inspect possible device client {p}: {e}")
    return found


class Suite:
    def __init__(self, args):
        self.a = args
        self.root = args.task_root.resolve()
        self.out = (args.output or self.root / "evidence" / ("bidirectional07_" + str(time.monotonic_ns()))).resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        self.bin = self.out / "bin"
        self.bin.mkdir()
        self.rows = []
        self.child = None
        self.unloaded = False
        self.summary = dict(result="running", task_root=str(self.root), output=str(self.out),
                            required_bit_version=hex(VERSION), board_test_executed=False,
                            coverage="RK H2C -> FPGA loop FIFO -> RK C2H; no FPGA display/color certification")

    def event(self, name, **fields):
        row = dict(event=name, **fields)
        with (self.out / "progress.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)

    def cmd(self, argv, log, timeout=30):
        with Path(log).open("w", encoding="utf-8") as f:
            p = subprocess.run([str(x) for x in argv], stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        if p.returncode:
            raise Failure(f"command rc={p.returncode}: {argv}; log={log}")

    def text(self, argv, timeout=20):
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        if p.returncode:
            raise Failure(f"{argv}: {p.stderr.strip()}")
        return p.stdout

    def regs(self):
        with self.user.open("r+b", buffering=0) as f, mmap.mmap(f.fileno(), 4096) as m:
            return {hex(o): struct.unpack_from("<I", m, o)[0] for o in REG_OFFSETS}

    def engine_state(self):
        # Actual anlogic_pci_lib.h: H2C0 base0; C2H0 base0x1000;
        # identifier+0, control+4, non-read-clear status+0x40, RUN/BUSY bit0.
        rows = {}
        with self.control.open("r+b", buffering=0) as f, mmap.mmap(f.fileno(), 8192) as m:
            for name, base, ident in (("h2c0", 0, 0x1fc0), ("c2h0", 0x1000, 0x1fc1)):
                values = [struct.unpack_from("<I", m, base + o)[0] for o in (0, 4, 0x40)]
                if values[0] >> 16 != ident or (values[0] >> 8) & 15:
                    raise Failure(f"{name} engine identifier mismatch: {values[0]:08x}")
                rows[name] = dict(identifier=hex(values[0]), control=hex(values[1]), status=hex(values[2]),
                                  run=bool(values[1] & 1), busy=bool(values[2] & 1))
        return rows

    def idle(self):
        r, e = self.regs(), self.engine_state()
        if r["0x5c"] != VERSION or r["0x60"] & 1 or r["0xa4"] & 1 or r["0x20"]:
            raise Failure(f"version/pipeline/mux/app-command not idle: {r}")
        if any(x["run"] or x["busy"] for x in e.values()):
            raise Failure(f"DMA engine not RUN0/BUSY0: {e}")
        return dict(registers=r, engines=e)

    def no_clients(self, include_video=True):
        paths = self.nodes + ([self.video] if include_video and self.video.exists() else [])
        found = active_clients(paths)
        if found:
            raise Failure(f"active device clients: {found}")

    def aer(self, dev, label, required):
        content = self.text(["lspci", "-vv", "-s", dev.name])
        (self.out / (label + "_lspci_" + dev.name.replace(":", "_") + ".txt")).write_text(content)
        lines = [s.strip() for s in content.splitlines() if re.search(r"\b(?:UESta|CESta):", s)]
        available = any("UESta:" in s for s in lines) and any("CESta:" in s for s in lines)
        if required and not available:
            raise Failure(f"AER status unavailable for endpoint {dev.name}")
        counters = {}
        for path in dev.glob("aer_dev_*"):
            value = path.read_text()
            (self.out / (label + "_" + dev.name.replace(":", "_") + "_" + path.name + ".txt")).write_text(value)
            for line in value.splitlines():
                fields = line.rsplit(None, 1)
                if len(fields) == 2 and fields[1].isdigit():
                    counters[path.name + ":" + fields[0]] = int(fields[1])
        return dict(bdf=dev.name, status_available=available, lines=lines, counters=counters,
                    asserted_flags=[f for line in lines for f in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\+", line)])

    def snapshot(self, label):
        mem = Path("/proc/meminfo").read_text()
        (self.out / (label + "_meminfo.txt")).write_text(mem)
        cma = {}
        for key in ("CmaTotal", "CmaFree"):
            match = re.search(r"^" + key + r":\s+(\d+)\s+kB$", mem, re.M)
            if not match:
                raise Failure(f"missing {key}")
            cma[key + "_kB"] = int(match.group(1))
        row = dict(cma=cma, idle=self.idle(), aer_endpoint=self.aer(self.ep, label, True))
        if self.rootport:
            row["aer_rootport"] = self.aer(self.rootport, label, False)
        dump(self.out / (label + "_state.json"), row)
        kernel = self.text(["dmesg", "--color=never"])
        (self.out / (label + "_dmesg.txt")).write_text(kernel)
        return row, kernel

    def discover(self):
        if sys.platform != "linux" or os.geteuid() != 0:
            raise Failure("run this board suite as root on RK Linux; --self-test is host-only")
        if b"rk3576" not in Path("/proc/device-tree/compatible").read_bytes():
            raise Failure("target is not RK3576")
        for module in ("anlogic_pci", "milianke_v4l2"):
            if not (Path("/sys/module") / module).exists():
                raise Failure(f"{module} must already be loaded by verified setup")
        self.v4l2_initial_loaded = True
        candidates = []
        for user in Path("/dev").glob("*_user"):
            prefix = str(user)[:-5]
            nodes = [Path(prefix + x) for x in ("_user", "_control", "_c2h_0", "_h2c_0")]
            if all(p.exists() and stat.S_ISCHR(p.stat().st_mode) for p in nodes):
                candidates.append((prefix, nodes))
        if len(candidates) != 1:
            raise Failure(f"expected unique user/control/C2H0/H2C0 device set, got {len(candidates)}")
        self.prefix, self.nodes = candidates[0]
        self.user, self.control = self.nodes[:2]
        videos = [Path("/dev") / p.parent.name for p in Path("/sys/class/video4linux").glob("video*/name")
                  if p.read_text().strip() == "Milianke PCIe Capture"]
        if len(videos) != 1:
            raise Failure(f"expected one Milianke V4L2 node, got {videos}")
        self.video = videos[0]
        eps = [p for p in Path("/sys/bus/pci/devices").glob("*") if (p / "vendor").exists()
               and (p / "vendor").read_text().strip() == "0x1edb"
               and (p / "device").read_text().strip() == "0xabcd"]
        if len(eps) != 1:
            raise Failure("expected one 1edb:abcd endpoint")
        self.ep = eps[0]
        parent = self.ep.resolve().parent
        self.rootport = Path("/sys/bus/pci/devices") / parent.name if re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", parent.name) else None
        self.no_clients()
        self.idle()
        options = Path("/sys/module/milianke_v4l2/parameters")
        self.module_options = [p.name + "=" + p.read_text().strip() for p in sorted(options.glob("*"))]
        ko_candidates = [self.a.v4l2_ko] if self.a.v4l2_ko else [self.root / "deploy/v4l2_drv/milianke_v4l2.ko", self.root / "fpga/deploy/v4l2_drv/milianke_v4l2.ko"]
        existing = [p.resolve() for p in ko_candidates if p and p.is_file()]
        if not existing:
            raise Failure("missing reloadable milianke_v4l2.ko; pass --v4l2-ko")
        if len({sha(p) for p in existing}) != 1:
            raise Failure("multiple different V4L2 ko candidates; select the deployed one with --v4l2-ko")
        self.ko = existing[0]
        if self.text(["modinfo", "-F", "vermagic", str(self.ko)]).split()[0] != os.uname().release:
            raise Failure("V4L2 ko kernel vermagic mismatch")
        if self.text(["modinfo", "-F", "name", str(self.ko)]).strip() != "milianke_v4l2":
            raise Failure("reload module name mismatch")
        for key, expected in (("poll_mode", "1"), ("enable_st_c2h_credit", "1"), ("desc_blen_max", "1048576")):
            if (Path("/sys/module/anlogic_pci/parameters") / key).read_text().strip() != expected:
                raise Failure(f"SGDMA {key} must be {expected}")
        self.summary.update(device_prefix=self.prefix, user=str(self.user), control=str(self.control),
                            video=str(self.video), endpoint=self.ep.name, v4l2_ko=str(self.ko),
                            v4l2_ko_sha256=sha(self.ko), v4l2_module_options=self.module_options)

    def prepare(self):
        source = self.out / "source/tools"
        source.mkdir(parents=True)
        (self.out / "source/evidence").mkdir()
        hashes = {}
        for name in ("image_roundtrip.c", "make_rgb_patterns.py"):
            original, frozen = self.root / "tools" / name, source / name
            shutil.copyfile(original, frozen)
            hashes[name] = sha(frozen)
            if hashes[name] != sha(original):
                raise Failure("source changed during snapshot")
        self.cmd(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", "-o", self.bin / "image_roundtrip", source / "image_roundtrip.c"], self.out / "image_roundtrip_compile.log", 60)
        self.cmd([sys.executable, "-m", "py_compile", source / "make_rgb_patterns.py"], self.out / "patterns_compile.log")
        self.cmd([sys.executable, source / "make_rgb_patterns.py"], self.out / "patterns_generate.log", 60)
        self.pattern_dir = self.out / "source/evidence"
        self.camera = self.a.camera_rgb.resolve()
        if not self.camera.is_file() or self.camera.stat().st_size not in (1280 * 720 * 3, 1920 * 1080 * 3):
            raise Failure("--camera-rgb must be one exact already captured 720p/1080p RGB24 frame")
        self.camera_hash = sha(self.camera)
        camera_copy = self.out / "source/camera_last.rgb"
        shutil.copyfile(self.camera, camera_copy)
        if sha(camera_copy) != self.camera_hash:
            raise Failure("camera frame changed during source snapshot")
        self.camera = camera_copy
        if shutil.disk_usage(self.out).free < 128 * 1024 * 1024:
            raise Failure("need 128 MiB output space for retained source/echo/log files")
        self.summary.update(source_sha256=hashes, executable_sha256=sha(self.bin / "image_roundtrip"),
                            camera_input=str(self.a.camera_rgb.resolve()), camera_sha256=self.camera_hash)

    def wait_child(self, timeout):
        try:
            rc = self.child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.child.terminate()
            try:
                self.child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                raise Failure("child remains stuck after SIGTERM; not using SIGKILL/forced unbind")
            raise Failure("image test timed out, SIGTERM cleanup attempted; test is failed")
        self.child = None
        return rc

    def roundtrip(self, label, source, frames, chunk):
        self.no_clients(False)
        before_idle = self.idle()
        directory = self.out / label
        directory.mkdir()
        echo, log = directory / "echo.rgb", directory / "transfer.log"
        distinct(source, echo)
        self.event("phase_start", phase=label, frames=frames, chunk=chunk)
        record = dict(phase=label, result="running", source=str(source), frames=frames, chunk_bytes=chunk, before_idle=before_idle)
        self.rows.append(record)
        with log.open("w", encoding="utf-8") as f:
            self.child = subprocess.Popen([str(self.bin / "image_roundtrip"), self.prefix, str(source), str(echo), str(frames), str(chunk), str(self.user)], stdout=f, stderr=subprocess.STDOUT)
            rc = self.wait_child(self.a.timeout)
        row = one_json(log.read_text(errors="replace"))
        record.update(tool_result=row, **validate_result(row, source, echo, frames, chunk, rc))
        record["after_idle"] = self.idle()
        record["result"] = "pass"
        dump(directory / "result.json", record)
        self.event("phase_pass", phase=label, exact_bytes=record["exact_bytes"], source_sha256=record["source_sha256"], echo_sha256=record["echo_sha256"])

    def interrupted_roundtrip(self, source):
        self.no_clients(False)
        self.idle()
        directory = self.out / "sigterm_1080"
        directory.mkdir()
        echo, log = directory / "partial_echo.rgb", directory / "transfer.log"
        distinct(source, echo)
        plan_frames, chunk = 100000, 1048576
        record = dict(phase="sigterm_1080", result="running", planned_frames=plan_frames, chunk_bytes=chunk)
        self.rows.append(record)
        before_kernel = self.text(["dmesg", "--color=never"])
        (directory / "before_dmesg.txt").write_text(before_kernel)
        with log.open("w", encoding="utf-8") as f:
            self.child = subprocess.Popen([str(self.bin / "image_roundtrip"), self.prefix, str(source), str(echo), str(plan_frames), str(chunk), str(self.user)], stdout=f, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self.child.poll() is not None:
                    raise Failure("large planned transfer ended before SIGTERM trigger")
                if echo.exists() and echo.stat().st_size >= chunk and self.regs()["0xa4"] & 1:
                    break
                time.sleep(.01)
            else:
                raise Failure("no actual received image data before SIGTERM deadline")
            record["signal_time_monotonic"] = time.monotonic()
            record["echo_bytes_at_signal"] = echo.stat().st_size
            record["engine_at_signal"] = self.engine_state()
            self.child.send_signal(signal.SIGTERM)
            rc = self.wait_child(30)
        row = one_json(log.read_text(errors="replace"))
        planned = Path(source).stat().st_size * plan_frames
        if rc != 1 or row.get("interrupted") is not True or row.get("failed") is not True or row.get("byte_mismatches") != 0:
            raise Failure(f"expected genuine interrupted return1 with no corrupted received bytes: {row}, rc={rc}")
        if not (0 < row.get("received", 0) < planned and row.get("sent", planned) < planned):
            raise Failure("SIGTERM did not interrupt an actual incomplete large transfer")
        record["tool_result"] = row
        record["after_idle"] = self.idle()
        # No client/module/reset action during this observation window.
        quiet_start = time.monotonic()
        quiet_samples = []
        while time.monotonic() - quiet_start < 12:
            quiet_samples.append(dict(seconds=time.monotonic() - quiet_start, state=self.idle()))
            time.sleep(.1)
        after_kernel = self.text(["dmesg", "--color=never"])
        (directory / "after_dmesg.txt").write_text(after_kernel)
        delta = kernel_delta(before_kernel, after_kernel)
        (directory / "kernel_delta.txt").write_text(delta)
        if POLL_ERROR.search(delta):
            raise Failure("residual poll timeout after SIGTERM")
        record.update(result="pass", quiet_seconds=time.monotonic() - quiet_start, quiet_samples=quiet_samples)
        dump(directory / "result.json", record)
        self.event("phase_pass", phase="sigterm_1080", quiet_seconds=record["quiet_seconds"], cleanup="mux0 CTRLdisabled RUN0 BUSY0")
        self.roundtrip("post_sigterm_known_first_frame", source, 1, 65536)

    def restore(self):
        if self.child is not None:
            if self.child.poll() is None:
                self.child.terminate()
                try:
                    self.child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    raise Failure("child still active; cannot safely restore V4L2; no force-unbind/SIGKILL")
            self.child = None
        module_present = Path("/sys/module/milianke_v4l2").exists()
        # A terminal signal can land immediately after successful rmmod but
        # before the Python flag assignment. Use actual presence as well.
        if not self.unloaded and not (getattr(self, "v4l2_initial_loaded", False) and not module_present):
            return
        if module_present:
            self.unloaded = False
            return
        self.unloaded = True
        self.no_clients(False)
        engines = self.engine_state()
        if any(e["run"] or e["busy"] for e in engines.values()):
            raise Failure("DMA still running/busy; refusing V4L2 reload")
        # Record actual child cleanup BEFORE these controlled safety/reset writes.
        self.summary["pre_restore_registers"] = self.regs()
        with self.user.open("r+b", buffering=0) as f, mmap.mmap(f.fileno(), 4096) as m:
            for offset, value in ((0xa4, 0), (0x20, 0), (0x60, 2), (0x90, 0)):
                struct.pack_into("<I", m, offset, value)
            if struct.unpack_from("<I", m, 0x90)[0] & 3:
                raise Failure("BAR CAM_MODE0 did not read back before V4L2 insmod")
        self.cmd(["insmod", self.ko] + self.module_options, self.out / "v4l2_reload.log", 30)
        self.unloaded = False
        if not Path("/sys/module/milianke_v4l2").exists():
            raise Failure("V4L2 module absent after successful insmod")
        deadline = time.monotonic() + 2
        while True:
            self.summary["restored_video_nodes"] = [str(p.parent.name) for p in Path("/sys/class/video4linux").glob("video*/name") if p.read_text().strip() == "Milianke PCIe Capture"]
            if len(self.summary["restored_video_nodes"]) == 1 and (Path("/dev") / self.summary["restored_video_nodes"][0]).exists():
                break
            if time.monotonic() >= deadline:
                raise Failure("expected unique sysfs and /dev V4L2 node after restoration")
            time.sleep(.05)
        if len(self.summary["restored_video_nodes"]) != 1:
            raise Failure("expected unique V4L2 node after restoration")
        self.summary["restoration"] = "V4L2 reloaded after BAR CAM_MODE0; SGDMA never unloaded"

    def run(self):
        rc, initial = 1, None
        try:
            self.discover()
            self.prepare()
            dump(self.out / "manifest.json", self.summary)
            initial, _ = self.snapshot("suite_before")
            if initial["cma"]["CmaTotal_kB"] < 65536:
                raise Failure("CMA total below required 64 MiB")
            if any(initial[key]["asserted_flags"] for key in ("aer_endpoint", "aer_rootport") if key in initial):
                raise Failure("preexisting AER flags; retain baseline and investigate before transfer")
            self.no_clients()
            self.cmd(["rmmod", "milianke_v4l2"], self.out / "v4l2_unload.log")
            self.unloaded = True
            if Path("/sys/module/milianke_v4l2").exists():
                raise Failure("V4L2 remained loaded after rmmod")
            self.summary["board_test_executed"] = True
            for label, w, h, frames, chunk in EXPECTED_PLAN:
                source = self.pattern_dir / f"pattern_{w}x{h}.rgb"
                if source.stat().st_size != w * h * 3:
                    raise Failure("known pattern size mismatch")
                self.roundtrip(label, source, frames, chunk)
            self.roundtrip("camera_actual_64K", self.camera, 3, 65536)
            self.interrupted_roundtrip(self.pattern_dir / "pattern_1920x1080.rgb")
            rc = 0
        except BaseException as e:
            self.summary.update(result="fail", reason=str(e))
            if self.rows and self.rows[-1]["result"] == "running":
                self.rows[-1].update(result="fail", reason=str(e))
                dump(self.out / self.rows[-1]["phase"] / "result.json", self.rows[-1])
            (self.out / "suite_failure.txt").write_text(traceback.format_exc())
        finally:
            # Further terminal signals must not skip the already-required join
            # and controlled module restoration after the first interruption.
            if sys.platform == "linux":
                signal.signal(signal.SIGINT, signal.SIG_IGN)
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
            try:
                self.restore()
            except BaseException as e:
                rc = 1
                self.summary["restore_error"] = str(e)
                (self.out / "restore_failure.txt").write_text(traceback.format_exc())
            if initial is not None and not self.unloaded:
                try:
                    after, _ = self.snapshot("suite_after")
                    loss = initial["cma"]["CmaFree_kB"] - after["cma"]["CmaFree_kB"]
                    checks = dict(cma_free_loss_kB=loss, allowed_cma_loss_kB=self.a.cma_leak_kb, aer={})
                    if loss > self.a.cma_leak_kb:
                        raise Failure(f"CMA loss {loss}kB exceeds {self.a.cma_leak_kb}kB")
                    for name in ("aer_endpoint", "aer_rootport"):
                        if name not in initial:
                            continue
                        b, a = initial[name], after[name]
                        increased = {k: v - b["counters"].get(k, 0) for k, v in a["counters"].items() if v > b["counters"].get(k, 0)}
                        checks["aer"][name] = dict(counter_increases=increased, before_flags=b["asserted_flags"], after_flags=a["asserted_flags"], status_available=a["status_available"])
                        if increased or b["asserted_flags"] or a["asserted_flags"]:
                            raise Failure(f"{name} asserted AER flags/counter increases")
                    self.summary["state_checks"] = checks
                except BaseException as e:
                    rc = 1
                    self.summary["final_state_error"] = str(e)
                    (self.out / "final_state_failure.txt").write_text(traceback.format_exc())
            if rc == 0 and len(self.rows) == 7 and all(x["result"] == "pass" for x in self.rows):
                self.summary["result"] = "bidirectional_complete_images_and_sigterm_recovery_pass"
            else:
                rc = 1
                self.summary["result"] = "fail"
            self.summary["phases"] = self.rows
            dump(self.out / "summary.json", self.summary)
            self.event("suite_result", result=self.summary["result"], output=str(self.out), reason=self.summary.get("reason"), restoration=self.summary.get("restoration"))
        return rc


def self_test():
    from types import SimpleNamespace
    from unittest.mock import patch
    cases = 0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source, echo = root / "source.rgb", root / "echo.rgb"
        source.write_bytes(bytes(range(256)) * 16)
        echo.write_bytes(source.read_bytes())
        row = dict(frames=3, frame_bytes=4096, chunk_bytes=4096, sent=12288, received=12288,
                   byte_mismatches=0, failed=False, interrupted=False, seconds=.1)
        validate_result(row, source, echo, 3, 4096, 0)
        cases += 1
        for key, value in (("frames", 2), ("frame_bytes", 4095), ("chunk_bytes", 65536),
                           ("sent", 12287), ("received", 12287), ("byte_mismatches", 1),
                           ("failed", True), ("interrupted", True)):
            bad = dict(row, **{key: value})
            try:
                validate_result(bad, source, echo, 3, 4096, 0)
            except Failure:
                cases += 1
            else:
                raise AssertionError(f"accepted bad {key}")
        for bad_echo in (b"short", b"x" * 4096):
            echo.write_bytes(bad_echo)
            try:
                validate_result(row, source, echo, 3, 4096, 0)
            except Failure:
                cases += 1
            else:
                raise AssertionError("accepted short/changed echo")
        try:
            distinct(source, source)
        except Failure:
            cases += 1
        else:
            raise AssertionError("accepted same path")
        os.link(source, root / "hardlink.rgb")
        try:
            distinct(source, root / "hardlink.rgb")
        except Failure:
            cases += 1
        else:
            raise AssertionError("accepted same inode")
        proc = root / "fake_proc"
        fake_pid = os.getpid() + 1000
        fake_fd = proc / str(fake_pid) / "fd/7"
        fake_fd.parent.mkdir(parents=True)
        os.link(source, fake_fd)
        with patch.object(os, "readlink", lambda path: str(source)):
            assert active_clients([source], proc) == [dict(pid=fake_pid, fd="7", target=str(source))]
            cases += 1
        fake_fd.unlink()
        assert active_clients([source], proc) == []
        cases += 1
        assert one_json("diagnostic\n" + json.dumps(row) + "\n") == row
        cases += 1
        try:
            one_json(json.dumps(row) + "\n" + json.dumps(row))
        except Failure:
            cases += 1
        else:
            raise AssertionError("accepted duplicate result")
        assert kernel_delta("old\n", "old\nnew\n") == "new\n"
        assert POLL_ERROR.search("engine_service_poll timeout")
        assert POLL_ERROR.search("poll completion timed out")
        assert not POLL_ERROR.search("normal transfer completed")
        cases += 4
        try:
            kernel_delta("old\n", "new\n")
        except Failure:
            cases += 1
        else:
            raise AssertionError("accepted unverifiable wrapped dmesg")
        # Real mmap of ordinary host files, never device MMIO. Check production
        # restore order and no-reload-on-BUSY; external module/sysfs are mocked.
        suite = Suite(SimpleNamespace(task_root=root, output=root / "mock_restore",
                                      cma_leak_kb=1024, timeout=30))
        suite.user, suite.control, suite.ko = root / "fake_user", root / "fake_control", root / "fake.ko"
        suite.user.write_bytes(bytes(4096)); suite.control.write_bytes(bytes(8192)); suite.ko.write_bytes(b"host mock")
        with suite.user.open("r+b") as f, mmap.mmap(f.fileno(), 4096) as m:
            struct.pack_into("<I", m, 0x5c, VERSION)
            struct.pack_into("<I", m, 0x90, 2)
        with suite.control.open("r+b") as f, mmap.mmap(f.fileno(), 8192) as m:
            struct.pack_into("<I", m, 0, 0x1fc00000)
            struct.pack_into("<I", m, 0x1000, 0x1fc10000)
        suite.unloaded = True; suite.v4l2_initial_loaded = True
        suite.module_options = []; suite.no_clients = lambda include_video=False: None
        fake_video = root / "video999/name"; fake_video.parent.mkdir(); fake_video.write_text("Milianke PCIe Capture\n")
        loaded = [False]; commands = []
        def fake_cmd(argv, log, timeout=30):
            assert argv[0] == "insmod" and suite.regs()["0x90"] == 0
            assert not any(x["run"] or x["busy"] for x in suite.engine_state().values())
            loaded[0] = True; commands.append(argv)
        suite.cmd = fake_cmd
        original_exists, original_glob = Path.exists, Path.glob
        def fake_exists(path):
            if path.as_posix() == "/sys/module/milianke_v4l2":
                return loaded[0]
            if path.as_posix() == "/dev/video999":
                return loaded[0]
            return original_exists(path)
        def fake_glob(path, pattern):
            if path.as_posix() == "/sys/class/video4linux":
                return iter([fake_video] if loaded[0] else [])
            return original_glob(path, pattern)
        with patch.object(Path, "exists", fake_exists), patch.object(Path, "glob", fake_glob):
            suite.restore()
            assert not suite.unloaded and len(commands) == 1 and suite.regs()["0x90"] == 0
            cases += 1
            # Reset mock state, introduce actual read BUSY1, and prove that no
            # CAM_MODE write or insmod happens while outstanding DMA is busy.
            loaded[0] = False; suite.unloaded = True
            with suite.user.open("r+b") as f, mmap.mmap(f.fileno(), 4096) as m:
                struct.pack_into("<I", m, 0x90, 2)
            with suite.control.open("r+b") as f, mmap.mmap(f.fileno(), 8192) as m:
                struct.pack_into("<I", m, 0x1040, 1)
            try:
                suite.restore()
            except Failure:
                assert len(commands) == 1 and suite.regs()["0x90"] == 2
                cases += 1
            else:
                raise AssertionError("restored while DMA BUSY1")
    print(json.dumps(dict(result="HOST_SELF_TEST_PASS_NOT_BOARD", cases=cases, board_test_executed=False)))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--task-root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--camera-rgb", type=Path, help="explicit path to one actual already captured camera RGB24 frame")
    p.add_argument("--v4l2-ko", type=Path)
    p.add_argument("--output", type=Path, help="new nonexistent output directory")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--cma-leak-kb", type=int, default=1024)
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if a.camera_rgb is None or a.timeout < 30 or a.cma_leak_kb < 0:
        p.error("--camera-rgb required; timeout>=30 and cma-leak-kb>=0")
    def interrupted(signo, frame):
        raise InterruptedError(f"suite interrupted by signal {signo}")
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    return Suite(a).run()


if __name__ == "__main__":
    raise SystemExit(main())
