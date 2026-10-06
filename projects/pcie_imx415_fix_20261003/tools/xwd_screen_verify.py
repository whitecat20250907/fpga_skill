#!/usr/bin/env python3
"""Decode actual XWD TrueColor pixels and verify stable Tk pattern ROIs.

Requires numpy; PNG encoding uses the standard library, not Pillow.
python3 xwd_screen_verify.py --xwd run/actual_0002.xwd --ready run/ready.json
  --events run/events.jsonl --out run/screen_check_0002
--decode-only deliberately reports UNVERIFIED, never screen-pattern PASS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib
import numpy as np

FIELDS = ('header_size file_version pixmap_format pixmap_depth pixmap_width pixmap_height '
          'xoffset byte_order bitmap_unit bitmap_bit_order bitmap_pad bits_per_pixel '
          'bytes_per_line visual_class red_mask green_mask blue_mask bits_per_rgb '
          'colormap_entries ncolors window_width window_height window_x window_y window_bdrwidth').split()


def mask_info(mask, bpp):
    if not mask or mask >> bpp:
        raise ValueError('RGB masks must be nonzero and within bits_per_pixel')
    shift = (mask & -mask).bit_length() - 1
    maximum = mask >> shift
    if maximum & (maximum + 1):
        raise ValueError('noncontiguous TrueColor mask is unsupported')
    return shift, maximum.bit_length(), maximum


def decode_xwd(data):
    if len(data) < 100:
        raise ValueError('truncated XWD header')
    header = dict(zip(FIELDS, struct.unpack_from('>25I', data)))
    hs, w, h = header['header_size'], header['pixmap_width'], header['pixmap_height']
    bpp, stride = header['bits_per_pixel'], header['bytes_per_line']
    if header['file_version'] != 7 or header['pixmap_format'] != 2:
        raise ValueError('only XWD version 7 ZPixmap is supported')
    if header['visual_class'] != 4:
        raise ValueError('only TrueColor visual is supported; palette/DirectColor needs explicit colormap handling')
    if bpp not in (8, 16, 24, 32) or header['byte_order'] not in (0, 1):
        raise ValueError('unsupported pixel bit depth or byte order')
    if header['xoffset'] != 0 or header['bitmap_unit'] not in (8, 16, 32) or header['bitmap_pad'] not in (8, 16, 32):
        raise ValueError('unsupported XImage offset/unit/padding')
    if hs < 100 or hs > len(data) or not w or not h or w * h > 33554432:
        raise ValueError('invalid header size or image dimensions')
    if header['pixmap_depth'] < 1 or header['pixmap_depth'] > bpp:
        raise ValueError('invalid pixmap_depth')
    nbytes = bpp // 8
    start = hs + header['ncolors'] * 12
    if stride < w * nbytes or start > len(data) or start + stride * h != len(data):
        raise ValueError('XWD row stride/colormap/payload length mismatch')
    masks = [header[k] for k in ('red_mask', 'green_mask', 'blue_mask')]
    if any(masks[i] & masks[j] for i in range(3) for j in range(i)):
        raise ValueError('overlapping RGB masks')
    info = [mask_info(mask, bpp) for mask in masks]
    if sum(bits for _, bits, _ in info) > header['pixmap_depth']:
        raise ValueError('RGB masks exceed pixmap depth')
    rows = np.frombuffer(data, dtype=np.uint8, offset=start).reshape(h, stride)
    packed = rows[:, :w * nbytes].reshape(h, w, nbytes)
    pixel = np.zeros((h, w), dtype=np.uint32)
    for byte in range(nbytes):
        shift = 8 * (byte if header['byte_order'] == 0 else nbytes - 1 - byte)
        pixel |= packed[:, :, byte].astype(np.uint32) << shift
    rgb = np.empty((h, w, 3), dtype=np.uint8)
    for channel, (mask, (shift, _, maximum)) in enumerate(zip(masks, info)):
        value = ((pixel & mask) >> shift).astype(np.uint64)
        rgb[:, :, channel] = (value * 255 + maximum // 2) // maximum
    header['window_name'] = data[100:hs].rstrip(b'\0').decode('utf-8', errors='replace')
    header['channel_bits'] = [bits for _, bits, _ in info]
    header['pixel_data_offset'] = start
    header['bitmap_bit_order_policy'] = 'ZPixmap byte-aligned pixel values use byte_order; no XY bitmap interpretation'
    header['rgb_policy'] = 'mask-code values scaled to RGB8; not HDMI panel gamma/colourimetry proof'
    return rgb, header


def save_png(path, rgb):
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError('PNG writer requires RGB uint8 HxWx3')
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    h, w, _ = rgb.shape
    compressor = zlib.compressobj(6)
    compressed = b''.join(compressor.compress(b'\0' + row.tobytes()) for row in rgb) + compressor.flush()
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', compressed) + chunk(b'IEND', b''))


def roi_pixels(rgb, box):
    if not isinstance(box, list) or len(box) != 4 or not all(type(v) is int for v in box):
        raise ValueError('ROI must contain four integer x0,y0,x1,y1 coordinates')
    x0, y0, x1, y1 = box
    if not 0 <= x0 < x1 <= rgb.shape[1] or not 0 <= y0 < y1 <= rgb.shape[0] or (x1 - x0) * (y1 - y0) < 16:
        raise ValueError('ROI is out of bounds or contains fewer than 16 pixels')
    return rgb[y0:y1, x0:x1]


def stats(pixels):
    values = pixels.reshape(-1, 3).astype(np.float64)
    normalized = values / 255
    linear = np.where(normalized <= 0.04045, normalized / 12.92, ((normalized + 0.055) / 1.055) ** 2.4)
    mean = values.mean(axis=0)
    return {'pixel_count': int(values.shape[0]), 'mean_rgb8': mean.tolist(),
            'median_rgb8': np.median(values, axis=0).tolist(), 'std_rgb8': values.std(axis=0).tolist(),
            'min_rgb8': values.min(axis=0).tolist(), 'max_rgb8': values.max(axis=0).tolist(),
            'clipped_low_fraction_by_channel': (values <= 5).mean(axis=0).tolist(),
            'clipped_high_fraction_by_channel': (values >= 250).mean(axis=0).tolist(),
            'srgb_inverse_transfer_mean': linear.mean(axis=0).tolist(),
            'linearization_assumption': 'sRGB inverse transfer only; actual camera ISP gamma is not verified',
            'mean_chroma_fraction': float((mean.max() - mean.min()) / max(mean.max(), 1))}


def read_pattern(ready_path, events_path, xwd_path, generation):
    ready = json.loads(ready_path.read_text(encoding='utf-8'))
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    gen = generation if generation is not None else ready.get('generation')
    rendered = [e for e in events if e.get('event') == 'rendered' and e.get('generation') == gen]
    captures = [e for e in events if e.get('event') == 'actual_xwd' and e.get('generation') == gen
                and Path(e.get('path', '')).name == xwd_path.name]
    if type(gen) is not int or gen < 1 or len(rendered) != 1 or len(captures) != 1:
        raise ValueError('unique rendered/captured generation evidence is missing')
    pattern, capture = rendered[0], captures[0]
    if capture.get('returncode') != 0 or capture.get('stable_generation') is not True:
        raise ValueError('actual XWD capture did not succeed in a stable command generation')
    if ready.get('generation') == gen and ready.get('reference_sha256') != pattern.get('reference_sha256'):
        raise ValueError('ready/events generation disagreement')
    # Source Unix paths remain meaningful when files are copied to Windows.
    if Path(capture['path']).parent != Path(pattern['reference_png']).parent:
        raise ValueError('capture and render evidence originate from different sessions')
    return pattern, capture


def self_test():
    golden = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 128, 0]],
                       [[0, 255, 255], [255, 0, 255], [0, 0, 0], [255, 255, 255]]], dtype=np.uint8)
    cases = 0
    for bpp, masks in ((24, (0xff0000, 0xff00, 0xff)), (32, (0xff, 0xff00, 0xff0000)), (16, (0xf800, 0x7e0, 0x1f))):
        for order in (0, 1):
            stride = golden.shape[1] * (bpp // 8) + 4
            payload = b''
            for row in golden:
                for source in row:
                    pixel = 0
                    for component, mask in zip(source, masks):
                        shift, _, maximum = mask_info(mask, bpp)
                        pixel |= ((int(component) * maximum + 127) // 255) << shift
                    payload += pixel.to_bytes(bpp // 8, 'little' if order == 0 else 'big')
                payload += b'\x5a' * 4
            header = [105, 7, 2, 16 if bpp == 16 else 24, 4, 2, 0, order, 32, 1 - order, 32,
                      bpp, stride, 4, *masks, 8, 256, 1, 4, 2, 0, 0, 0]
            encoded = struct.pack('>25I', *header) + b'test\0' + bytes(12) + payload
            decoded, _ = decode_xwd(encoded)
            if bpp != 16:
                assert np.array_equal(decoded, golden)
            else:
                assert np.max(np.abs(decoded.astype(int) - golden.astype(int))) <= 4
            for index, value in ((2, 1), (13, 3), (6, 1), (15, masks[0]), (12, 1)):
                bad = header.copy(); bad[index] = value
                try:
                    decode_xwd(struct.pack('>25I', *bad) + b'test\0' + bytes(12) + payload)
                except ValueError:
                    pass
                else:
                    raise AssertionError('unsupported/invalid XWD accepted')
            cases += 1
    print('PASS_XWD_SYNTHETIC_ONLY formats=6 negative_checks=30; no actual screen evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xwd', type=Path)
    parser.add_argument('--ready', type=Path)
    parser.add_argument('--events', type=Path)
    parser.add_argument('--generation', type=int)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--decode-only', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    if args.xwd is None or args.out is None or (not args.decode_only and args.ready is None):
        parser.error('--xwd/--out required; verification also requires --ready')
    args.out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'UNRESOLVED', 'actual_xwd': str(args.xwd),
              'scope': 'actual X11 window pixel evidence; not physical HDMI colourimetry or camera pipeline PASS'}
    try:
        raw = args.xwd.read_bytes()
        rgb, header = decode_xwd(raw)
        report.update(xwd_sha256=hashlib.sha256(raw).hexdigest(), header=header,
                      actual_rgb8_sha256=hashlib.sha256(rgb.tobytes()).hexdigest())
        save_png(args.out / 'decoded_actual.png', rgb)
        if args.decode_only:
            report['status'] = 'DECODED_ACTUAL_UNVERIFIED'
            passed = True  # Decode success only, explicitly not verification.
        else:
            event_path = args.events or args.ready.with_name('events.jsonl')
            pattern, capture = read_pattern(args.ready, event_path, args.xwd, args.generation)
            if rgb.shape[1::-1] != tuple(pattern['screen_bounds'][2:4]):
                raise ValueError('actual screenshot dimensions do not match rendered monitor window')
            if header['channel_bits'] != [8, 8, 8]:
                raise ValueError('exact nominal RGB8 verification requires eight bits per channel; decoded PNG retained')
            results = []
            for item in pattern['patches']:
                pixels = roi_pixels(rgb, item['sample_roi'])
                expected = np.array(item['rgb'], dtype=np.uint8)
                if expected.shape != (3,):
                    raise ValueError('expected RGB metadata must contain three channels')
                error = np.abs(pixels.astype(int) - expected.astype(int))
                results.append({'name': item['name'], 'roi': item['sample_roi'], 'expected_rgb8': item['rgb'],
                                'stats': stats(pixels), 'max_channel_error': error.max(axis=(0, 1)).tolist(),
                                'mismatched_pixel_count': int(np.any(error != 0, axis=2).sum()),
                                'exact_rgb8': bool(np.all(error == 0))})
            passed = bool(results) and all(r['exact_rgb8'] for r in results)
            report.update(status='PASS_X11_WINDOW_PATCH_RGB8' if passed else 'FAIL_X11_WINDOW_PATCH_RGB8',
                          generation=pattern['generation'], command=pattern['command'], patches=results,
                          capture_event=capture, ready_sha256=hashlib.sha256(args.ready.read_bytes()).hexdigest(),
                          events_sha256=hashlib.sha256(event_path.read_bytes()).hexdigest(),
                          reference_png_opened_or_used_as_actual_pixels=False)
    except Exception as exc:
        report.update(status='UNRESOLVED_ERROR', error=str(exc)); passed = False
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'out': str(args.out), 'error': report.get('error')}))
    return 0 if passed else 2


if __name__ == '__main__':
    sys.exit(main())
