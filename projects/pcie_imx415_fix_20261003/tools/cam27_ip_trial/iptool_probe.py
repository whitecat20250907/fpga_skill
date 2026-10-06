"""Run only explicitly selected IpTool CLI probes, hidden and bounded.

This is a shadow IP generation experiment. It never modifies FPGA source.
"""
from pathlib import Path
import json
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
TD = Path("E:/qianrufpga/TD")
args = sys.argv[1:]
label = args.pop(0)
executable = "IpTool.exe"
if args and args[0] == "--exe":
    args.pop(0)
    executable = args.pop(0)
command = [str(TD / "bin" / executable), *args]
si = subprocess.STARTUPINFO()
si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
si.wShowWindow = subprocess.SW_HIDE
start = time.monotonic()
p = subprocess.Popen(command, cwd=BASE, stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
timed_out = False
try:
    out, err = p.communicate(timeout=20)
except subprocess.TimeoutExpired:
    timed_out = True
    # Kill only the probe's own process tree, never a user's TD session.
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                   capture_output=True, startupinfo=si,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    out, err = p.communicate(timeout=5)
meta = {"command": command, "pid": p.pid, "returncode": p.returncode,
        "timed_out": timed_out, "elapsed_seconds": round(time.monotonic()-start, 3)}
(BASE / (label + ".json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")
(BASE / (label + ".stdout.log")).write_bytes(out)
(BASE / (label + ".stderr.log")).write_bytes(err)
print(json.dumps(meta, indent=2))
print(out.decode("utf-8", errors="replace")[:10000])
print(err.decode("utf-8", errors="replace")[:10000])
