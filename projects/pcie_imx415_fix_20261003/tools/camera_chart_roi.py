#!/usr/bin/env python3
"""Measure manually supplied camera colour-chart centre ROIs; no localisation.

python camera_chart_roi.py --image camera.png --boxes manual_boxes.json --out new_dir
Boxes: {"coordinate_system":"pixels_xyxy","patches":[{"name":"RED","box":[x0,y0,x1,y1]}, ...]}.
Requires numpy/opencv; raw .rgb input also requires --width/--height (RGB24).
Does not rotate, resize, white-balance or modify pixels used for statistics.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import cv2
import numpy as np
from xwd_screen_verify import roi_pixels, stats

NAMES = ('RED', 'GREEN', 'BLUE', 'WHITE', 'GRAY', 'BLACK', 'ORANGE', 'CYAN', 'MAGENTA')
PAIRS = {'RED': ((0, 1), (0, 2)), 'GREEN': ((1, 0), (1, 2)), 'BLUE': ((2, 0), (2, 1)),
         'ORANGE': ((0, 1), (1, 2)), 'CYAN': ((1, 0), (2, 0)), 'MAGENTA': ((0, 1), (2, 1))}


def order_checks(name, measured, raw_margin, linear_margin, minimum_brightness):
    if name not in PAIRS:
        return {'status': 'NEUTRAL_NO_CHANNEL_ORDER_EXPECTED', 'pairs': [], 'passed': None}
    raw = measured['mean_rgb8']
    linear = measured['srgb_inverse_transfer_mean']
    pairs = [{'greater': 'RGB'[hi], 'less': 'RGB'[lo], 'raw_difference': raw[hi] - raw[lo],
              'assumed_srgb_linear_difference': linear[hi] - linear[lo],
              'raw_ratio': raw[hi] / max(raw[lo], 1.0),
              'raw_pass': raw[hi] > raw[lo] and raw[hi] - raw[lo] >= raw_margin,
              'assumed_linear_pass': linear[hi] > linear[lo] and linear[hi] - linear[lo] >= linear_margin}
             for hi, lo in PAIRS[name]]
    dark = max(raw) < minimum_brightness
    passed = not dark and all(p['raw_pass'] and p['assumed_linear_pass'] for p in pairs)
    return {'status': 'INCONCLUSIVE_DARK' if dark else ('SUPPORTS_EXPECTED_ORDER' if passed else 'DOES_NOT_SUPPORT_EXPECTED_ORDER'),
            'passed': passed, 'pairs': pairs}


def load_rgb(path, width, height):
    if path.suffix.lower() == '.rgb':
        data = path.read_bytes()
        if not width or not height or width * height * 3 != len(data):
            raise ValueError('raw RGB24 requires exact --width/--height and matching byte length')
        return np.frombuffer(data, np.uint8).reshape(height, width, 3).copy()
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] not in (3, 4):
        raise ValueError('camera image must be an actual uint8 3/4-channel image or explicit RGB24 file')
    # OpenCV returns BGR/BGRA. Conversion is explicit before every measurement.
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB if image.shape[2] == 3 else cv2.COLOR_BGRA2RGB)


def analyse(rgb, definition, allow_partial, raw_margin, linear_margin, minimum_brightness):
    if definition.get('coordinate_system', 'pixels_xyxy') != 'pixels_xyxy':
        raise ValueError('unsupported ROI coordinate system')
    items = definition.get('patches')
    if not isinstance(items, list) or not items:
        raise ValueError('no manually supplied patch ROIs')
    names, boxes, results = [], [], []
    for item in items:
        name = str(item['name']).upper()
        if name not in NAMES or name in names:
            raise ValueError('unknown or duplicate patch name: ' + name)
        box = item['box']
        pixels = roi_pixels(rgb, box)
        for other in boxes:
            if max(box[0], other[0]) < min(box[2], other[2]) and max(box[1], other[1]) < min(box[3], other[3]):
                raise ValueError('manual centre ROIs overlap; distinct patches must have distinct sample pixels')
        measured = stats(pixels)
        results.append({'name': name, 'box': box, 'statistics': measured,
                        'channel_order': order_checks(name, measured, raw_margin, linear_margin, minimum_brightness)})
        names.append(name); boxes.append(box)
    missing = sorted(set(NAMES) - set(names))
    if missing and not allow_partial:
        raise ValueError('missing manual boxes for: ' + ', '.join(missing) + '; use --allow-partial for explicitly partial analysis')
    tested = [r for r in results if r['name'] in PAIRS]
    full = not missing
    all_order = bool(tested) and all(r['channel_order']['passed'] for r in tested)
    neutral = {}
    by_name = {r['name']: r for r in results}
    if all(n in by_name for n in ('WHITE', 'GRAY', 'BLACK')):
        brightness = {n: float(np.dot(by_name[n]['statistics']['mean_rgb8'], (0.2126, 0.7152, 0.0722)))
                      for n in ('WHITE', 'GRAY', 'BLACK')}
        neutral = {'mean_encoded_luma': brightness,
                   'white_gt_gray_gt_black': brightness['WHITE'] > brightness['GRAY'] > brightness['BLACK']}
    return {'status': ('FULL_CHART_CHANNEL_ORDER_SUPPORT' if all_order and neutral.get('white_gt_gray_gt_black')
                       else 'FULL_CHART_CHANNEL_ORDER_NOT_ESTABLISHED') if full else 'PARTIAL_MEASUREMENT_ONLY',
            'patches': results, 'missing_patch_names': missing, 'full_chart_scope': full,
            'all_tested_colour_order_checks_passed': all_order, 'neutral_brightness': neutral,
            'thresholds': {'minimum_raw_channel_difference': raw_margin,
                           'minimum_assumed_srgb_linear_difference': linear_margin,
                           'minimum_brightest_raw_channel': minimum_brightness},
            'scope': 'channel-order evidence in manual camera ROIs; not calibrated colour accuracy, model accuracy or whole-system PASS',
            'geometry_policy': 'manual original-image centre boxes; no automatic chart identification, rotation or resizing',
            'linearization_policy': 'raw statistics plus explicitly assumed sRGB inverse transfer; actual ISP gamma not verified'}


def annotate(rgb, results):
    image = cv2.cvtColor(rgb.copy(), cv2.COLOR_RGB2BGR)
    for index, result in enumerate(results):
        x0, y0, x1, y1 = result['box']
        # These are BGR drawing colours only, never measurement input.
        outline = (0, 255, 0) if result['channel_order'].get('passed') else (0, 165, 255)
        cv2.rectangle(image, (x0, y0), (x1 - 1, y1 - 1), outline, 1)
        means = result['statistics']['mean_rgb8']
        label = '%s R%.0f G%.0f B%.0f' % (result['name'], *means)
        y_text = y0 - 4 if y0 >= 16 else min(image.shape[0] - 4, y1 + 14)
        cv2.putText(image, label, (max(0, x0), y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(image, label, (max(0, x0), y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.38, outline, 1, cv2.LINE_AA)
    return image


def self_test():
    rgb = np.zeros((90, 90, 3), dtype=np.uint8)
    values = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255), (128, 128, 128),
              (0, 0, 0), (255, 128, 0), (0, 255, 255), (255, 0, 255))
    items = []
    for i, (name, value) in enumerate(zip(NAMES, values)):
        row, col = divmod(i, 3); x, y = col * 30, row * 30
        rgb[y:y + 30, x:x + 30] = value
        items.append({'name': name, 'box': [x + 8, y + 8, x + 22, y + 22]})
    definition = {'patches': items}
    good = analyse(rgb, definition, False, 5, 0.01, 8)
    assert good['status'] == 'FULL_CHART_CHANNEL_ORDER_SUPPORT'
    bad = analyse(rgb[:, :, [1, 0, 2]], definition, False, 5, 0.01, 8)
    assert not bad['all_tested_colour_order_checks_passed']
    dark = analyse(rgb * 0, definition, False, 5, 0.01, 8)
    assert all(r['channel_order']['status'] == 'INCONCLUSIVE_DARK' for r in dark['patches'] if r['name'] in PAIRS)
    gray = rgb.copy()
    for item in items:
        if item['name'] in PAIRS:
            x0, y0, x1, y1 = item['box']; gray[y0:y1, x0:x1] = 128
    assert not analyse(gray, definition, False, 0, 0, 8)['all_tested_colour_order_checks_passed']
    try:
        analyse(rgb, {'patches': [items[0]]}, False, 5, 0.01, 8)
    except ValueError:
        pass
    else:
        raise AssertionError('partial chart silently accepted as full')
    print('PASS_SYNTHETIC_CAMERA_ROIS positive/RG-swap/dark/neutral-zero-margin/partial; no actual camera acceptance')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--boxes', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int)
    parser.add_argument('--raw-margin', type=float, default=5)
    parser.add_argument('--linear-margin', type=float, default=0.01)
    parser.add_argument('--min-brightness', type=float, default=8)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    if args.image is None or args.boxes is None or args.out is None:
        parser.error('--image/--boxes/--out are required')
    if (not all(math.isfinite(v) for v in (args.raw_margin, args.linear_margin, args.min_brightness))
            or args.raw_margin < 0 or args.linear_margin < 0 or args.min_brightness <= 0):
        parser.error('margins must be nonnegative; min-brightness positive')
    args.out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'UNRESOLVED_ERROR'}
    try:
        rgb = load_rgb(args.image, args.width, args.height)
        definition = json.loads(args.boxes.read_text(encoding='utf-8'))
        report = analyse(rgb, definition, args.allow_partial, args.raw_margin, args.linear_margin, args.min_brightness)
        report.update(image=str(args.image), dimensions=[rgb.shape[1], rgb.shape[0]],
                      source_sha256=hashlib.sha256(args.image.read_bytes()).hexdigest(),
                      decoded_original_rgb8_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                      boxes_sha256=hashlib.sha256(args.boxes.read_bytes()).hexdigest())
        if not cv2.imwrite(str(args.out / 'annotated_actual_camera.png'), annotate(rgb, report['patches'])):
            raise RuntimeError('annotated PNG save failed')
    except Exception as exc:
        report.update(status='UNRESOLVED_ERROR', error=str(exc))
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'out': str(args.out), 'error': report.get('error')}))
    return 0 if report['status'] in ('FULL_CHART_CHANNEL_ORDER_SUPPORT', 'PARTIAL_MEASUREMENT_ONLY') else 2


if __name__ == '__main__':
    sys.exit(main())
