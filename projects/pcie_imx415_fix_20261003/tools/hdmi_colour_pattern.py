#!/usr/bin/env python3
"""Known RGB Tk/X11 chart, without modesetting or stopping the desktop.

DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 python3 hdmi_colour_pattern.py 
  --output HDMI-1 --control /tmp/hdmi_control.json --out /tmp/hdmi_pattern_run

Atomically replace control JSON with {"mode":"solid","colour":"RED","id":"red1"},
{"mode":"chart","id":"chart1"}, or {"mode":"quit"}. Escape/SIGTERM also close
only this window. --capture-xwd optionally saves actual X11 window pixels.
Reference PNGs are generated from explicit RGB values, not camera pictures.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import signal
import struct
import subprocess
import sys
import threading
import time
import zlib

COLOURS = [('RED', (255, 0, 0)), ('GREEN', (0, 255, 0)), ('BLUE', (0, 0, 255)),
           ('WHITE', (255, 255, 255)), ('GRAY', (128, 128, 128)), ('BLACK', (0, 0, 0)),
           ('ORANGE', (255, 128, 0)), ('CYAN', (0, 255, 255)), ('MAGENTA', (255, 0, 255))]


def colour(value):
    if isinstance(value, str):
        named = dict(COLOURS).get(value.upper())
        if named is not None:
            return named
        if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    if isinstance(value, list) and len(value) == 3 and all(type(x) is int and 0 <= x <= 255 for x in value):
        return tuple(value)
    raise ValueError('colour must be RED/GREEN/... or #RRGGBB or three integer RGB channels')


def hex_rgb(rgb):
    return '#%02x%02x%02x' % rgb


def bounds(text):
    match = re.fullmatch(r'(\d+)x(\d+)\+(\d+)\+(\d+)', text)
    if not match:
        raise ValueError('geometry must be WIDTHxHEIGHT+X+Y with nonnegative X11 coordinates')
    result = tuple(map(int, match.groups()))
    if result[0] < 48 or result[1] < 48:
        raise ValueError('monitor bounds must be at least 48x48')
    return result


def patches(width, height, command):
    mode = command.get('mode', 'chart')
    if mode == 'solid':
        items = [(str(command.get('label', command.get('colour', 'SOLID'))), colour(command.get('colour', 'WHITE')), (0, 0, width, height))]
    elif mode == 'chart':
        items = [(name, rgb, (col * width // 3, row * height // 3,
                             (col + 1) * width // 3, (row + 1) * height // 3))
                 for i, (name, rgb) in enumerate(COLOURS) for row, col in [divmod(i, 3)]]
    else:
        raise ValueError('mode must be chart, solid or quit')
    result = []
    for name, rgb, (x0, y0, x1, y1) in items:
        dx, dy = x1 - x0, y1 - y0
        result.append({'name': name, 'rgb': rgb, 'hex': hex_rgb(rgb),
                       'rect': [x0, y0, x1, y1],
                       'sample_roi': [x0 + dx * 3 // 10, y0 + dy * 3 // 10,
                                      x0 + dx * 7 // 10, y0 + dy * 7 // 10]})
    return result


def png_bytes(width, height, items):
    # RGB24 PNG, no guessed BGR/ARGB storage. Labels are separate Tk overlays;
    # sample ROIs are at patch centres and exclude all label pixels.
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    rows = []
    for y in range(height):
        row = bytearray(width * 3)
        for item in items:
            x0, y0, x1, y1 = item['rect']
            if y0 <= y < y1:
                row[x0 * 3:x1 * 3] = bytes(item['rgb']) * (x1 - x0)
        rows.append(b'\0' + row)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(rows), 1)) + chunk(b'IEND', b''))


def atomic_json(path, data):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def self_test():
    items = patches(60, 60, {'mode': 'chart'})
    raw = png_bytes(60, 60, items)
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    compressed = b''
    cursor = 8
    while cursor < len(raw):
        length, = struct.unpack_from('>I', raw, cursor)
        kind, payload = raw[cursor + 4:cursor + 8], raw[cursor + 8:cursor + 8 + length]
        assert zlib.crc32(kind + payload) & 0xffffffff == struct.unpack_from('>I', raw, cursor + 8 + length)[0]
        if kind == b'IDAT':
            compressed += payload
        cursor += length + 12
    pixels = zlib.decompress(compressed)
    for item in items:
        x0, y0, x1, y1 = item['sample_roi']
        offset = ((y0 + y1) // 2) * 181 + 1 + ((x0 + x1) // 2) * 3
        assert pixels[offset:offset + 3] == bytes(item['rgb'])
    assert colour('#ff8000') == (255, 128, 0)
    assert colour('BLUE') == (0, 0, 255)
    assert bounds('1920x1080+0+0') == (1920, 1080, 0, 0)
    for bad in ('1920x1080-1+0', '0x1080+0+0'):
        try:
            bounds(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('bad geometry accepted')
    print('PASS_PATTERN_RGB_PNG_ROIS_AND_GEOMETRY; no X11/board test')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='HDMI-1')
    parser.add_argument('--geometry', help='explicit WIDTHxHEIGHT+X+Y, otherwise exact xrandr output lookup')
    parser.add_argument('--control', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--capture-xwd', action='store_true')
    parser.add_argument('--seconds', type=float, default=600)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.control is None or args.out is None or not 0 < args.seconds <= 3600:
        parser.error('--control, --out and 0 < --seconds <= 3600 required')
    import tkinter as tk
    xr = subprocess.run(['xrandr', '--query'], capture_output=True, text=True, timeout=10, check=True).stdout
    if args.geometry:
        geometry = args.geometry
    else:
        line = next((line for line in xr.splitlines() if line.startswith(args.output + ' connected')), None)
        match = re.search(r'\d+x\d+[+-]\d+[+-]\d+', line or '')
        if not match:
            raise RuntimeError('requested X11 output has no active exact geometry; refusing a guessed monitor')
        geometry = match.group(0)
    width, height, x, y = bounds(geometry)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'pid').write_text(str(os.getpid()) + '\n', encoding='ascii')
    (args.out / 'xrandr.txt').write_text(xr, encoding='utf-8')
    root = tk.Tk()
    root.withdraw()
    root.title('FPGA known RGB calibration pattern')
    # Exact monitor-sized borderless window, not WM fullscreen across the
    # whole 1920x1280 desktop. No RR modeset, DRM master or lightdm changes.
    root.overrideredirect(True)
    root.geometry(geometry)
    root.attributes('-topmost', True)
    canvas = tk.Canvas(root, width=width, height=height, highlightthickness=0, borderwidth=0)
    canvas.pack(fill='both', expand=True)
    root.deiconify()
    root.lift()
    root.update_idletasks()
    session = {'pid': os.getpid(), 'window_id': root.winfo_id(), 'output': args.output,
               'geometry': geometry, 'screen_bounds': [x, y, width, height],
               'desktop_bounds': [root.winfo_screenwidth(), root.winfo_screenheight()],
               'display': os.environ.get('DISPLAY'), 'xauthority_path': os.environ.get('XAUTHORITY'),
               'other_overlapping_outputs_may_show_the_same_pattern': True,
               'mode_policy': 'no_modeset_no_lightdm_stop_window_destroy_restores_desktop',
               'reference_policy': 'nominal_RGB24_patches_without_Tk_text; optional_actual_X11_xwd',
               'started_unix': time.time()}
    atomic_json(args.out / 'session.json', session)
    events = (args.out / 'events.jsonl').open('x', encoding='utf-8', buffering=1)
    stop = False
    generation = 0
    prior_bytes = None
    started = time.monotonic()
    messages = queue.Queue()

    def log(event):
        event['unix'] = time.time()
        events.write(json.dumps(event, ensure_ascii=False) + '\n')
        print(json.dumps(event, ensure_ascii=False), flush=True)

    def request_stop(*_):
        nonlocal stop
        stop = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)
    root.bind('<Escape>', request_stop)
    root.protocol('WM_DELETE_WINDOW', request_stop)

    def capture_xwd(number, window, target):
        # Only this child belongs to this process; do not kill/match unrelated
        # background processes. A changed generation invalidates correlation.
        try:
            result = subprocess.run(['xwd', '-silent', '-id', str(window), '-out', str(target)],
                                    capture_output=True, text=True, timeout=5)
            messages.put({'event': 'actual_xwd', 'generation': number, 'returncode': result.returncode,
                          'path': str(target), 'stable_generation': number == generation,
                          'stderr': result.stderr[-500:]})
        except Exception as exc:
            messages.put({'event': 'actual_xwd_error', 'generation': number, 'error': str(exc)})

    def render(command):
        nonlocal generation
        generation += 1
        items = patches(width, height, command)
        canvas.delete('all')
        for item in items:
            x0, y0, x1, y1 = item['rect']
            canvas.create_rectangle(x0, y0, x1, y1, fill=item['hex'], outline=item['hex'], width=0)
            luminance = sum(a * b for a, b in zip(item['rgb'], (0.2126, 0.7152, 0.0722)))
            text_colour = '#000000' if luminance > 144 else '#ffffff'
            label = item['name'] + '  ' + item['hex'].upper()
            canvas.create_text((x0 + x1) / 2, y0 + (y1 - y0) * 0.13, text=label,
                               fill=text_colour, font=('DejaVu Sans', max(18, (y1 - y0) // 12), 'bold'), anchor='center')
        root.update_idletasks()
        png = png_bytes(width, height, items)
        path = args.out / ('reference_%04d.png' % generation)
        path.write_bytes(png)
        metadata = {'event': 'rendered', 'generation': generation, 'command': command,
                    'screen_bounds': [x, y, width, height], 'patches': items,
                    'reference_png': str(path), 'reference_sha256': hashlib.sha256(png).hexdigest(),
                    'window_id': root.winfo_id(), 'actual_HDMI_colourimetry_verified': False}
        atomic_json(args.out / 'ready.json', metadata)
        log(metadata)
        if args.capture_xwd:
            threading.Thread(target=capture_xwd, args=(generation, root.winfo_id(),
                             args.out / ('actual_%04d.xwd' % generation)), daemon=True).start()

    def poll():
        nonlocal prior_bytes, stop
        while not messages.empty():
            log(messages.get_nowait())
        if stop or time.monotonic() - started >= args.seconds:
            root.destroy()
            return
        try:
            data = args.control.read_bytes()
            if data != prior_bytes:
                command = json.loads(data)
                if not isinstance(command, dict):
                    raise ValueError('control must be a JSON object')
                if command.get('mode') == 'quit':
                    log({'event': 'quit_command'})
                    stop = True
                else:
                    render(command)
                prior_bytes = data
        except FileNotFoundError:
            pass
        except Exception as exc:
            log({'event': 'control_or_render_error', 'error': str(exc)})
            # Retry only when bytes change, while keeping the existing valid
            # image visible. Prefer atomic control-file replacement.
            if 'data' in locals():
                prior_bytes = data
        root.after(100, poll)

    try:
        render({'mode': 'chart', 'id': 'initial'})
        root.after(100, poll)
        root.mainloop()
    finally:
        log({'event': 'window_closed', 'desktop_window_restoration': 'this_test_window_destroyed',
             'no_video_mode_or_desktop_service_changed': True})
        events.close()
        session['ended_unix'] = time.time()
        atomic_json(args.out / 'session.json', session)
    return 0


if __name__ == '__main__':
    sys.exit(main())
