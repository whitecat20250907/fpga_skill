"""Serial RPC for the RK CH9102 console; append RX evidence to a local log."""
import sys
import json
import time
import base64
import shlex
import hashlib
from pathlib import Path
import serial

port = sys.argv[1] if len(sys.argv)>1 else 'COM12'
uart = serial.Serial(port, 1500000, timeout=0.1, write_timeout=5)
log = Path(__file__).resolve().parents[1] / 'evidence/rk_serial.log'
print('SERIAL_READY', flush=True)
for line in sys.stdin:
    try:
        req = json.loads(line)
        is_get = req.get('op') == 'get'
        if is_get:
            remote = req['remote']
            assert remote.startswith('/home/linaro/pcie_fix_20261003/')
            uart.write(("printf '\\nCODEX_FILE_BEGIN\\n'; base64 -w0 " + shlex.quote(remote) + "; printf '\\nCODEX_FILE_END\\n'\r").encode())
        if req.get('op') == 'put':
            remote = req['remote']
            assert remote.startswith('/home/linaro/pcie_fix_20261003/')
            payload = base64.b64encode(Path(req['local']).read_bytes()).decode()
            uart.write(("stty -echo; PS2=''; base64 -d > " + shlex.quote(remote) + " <<'CODEX_B64'\r").encode())
            time.sleep(.3)
            for at in range(0, len(payload), 256):
                uart.write((payload[at:at+256]+'\r').encode())
                time.sleep(.035)
            uart.write(('CODEX_B64\rstty echo; sha256sum '+shlex.quote(remote)+'\r').encode())
        if req.get('op') == 'baud':
            uart.baudrate = req['baud']
        if 'send' in req:
            uart.write(req['send'].encode())
        until = time.monotonic() + min(req.get('seconds', 2), 15)
        data = bytearray()
        while time.monotonic()<until:
            data += uart.read(max(uart.in_waiting, 1))
            if is_get and b'\nCODEX_FILE_END\r' in data:
                break
        if is_get:
            payload=data.split(b'\nCODEX_FILE_BEGIN\r\n',1)[1].split(b'\r\nCODEX_FILE_END',1)[0]
            decoded=base64.b64decode(payload, validate=True)
            Path(req['local']).write_bytes(decoded)
            print(json.dumps({'saved':req['local'], 'bytes':len(decoded), 'sha256':hashlib.sha256(decoded).hexdigest()}),flush=True)
            continue
        with log.open('ab') as f:
            f.write(data)
        decoded=data.decode(errors='replace')
        print(json.dumps({'rx':decoded[-req.get('max_chars',7000):], 'rx_bytes':len(data)}, ensure_ascii=False), flush=True)
    except Exception as error:
        print(json.dumps({'error':str(error)}, ensure_ascii=False), flush=True)
