#!/usr/bin/env python3
"""
rk3576_yolov5s_relu.py
YOLOv5s-Relu 实时推理 — 适配 RK3576 + MIPI 输入(/dev/video22)
模型输出: 3 个原始特征图 (1,255,80/40/20,80/40/20)，需按 anchors 解码
OpenCV 支持 GUI 则弹居中窗口，否则定时存图兜底
"""

import cv2
import numpy as np
import time
from rknnlite.api import RKNNLite

DEVICE       = '/dev/video22'
WIDTH        = 1920
HEIGHT       = 1080
FPS          = 30
MODEL_PATH   = 'yolov5s_relu.rknn'
IMG_SIZE     = 640
SAVE_EVERY   = 30
SAVE_PATH    = '/home/rock/yolo/det.jpg'

CLASS_NAMES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
    'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
    'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
    'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
    'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
    'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
    'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
    'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
    'hair drier', 'toothbrush'
]

OBJ_THRESH  = 0.35
NMS_THRESH  = 0.45

MASKS   = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
ANCHORS = [[10, 13], [16, 30], [33, 23], [30, 61], [62, 45],
           [59, 119], [116, 90], [156, 198], [373, 326]]


def letterbox(img, new_shape=640, color=(0, 0, 0)):
    h, w = img.shape[:2]
    r = min(new_shape / h, new_shape / w)
    new_w, new_h = int(w * r), int(h * r)
    dw = (new_shape - new_w) / 2
    dh = (new_shape - new_h) / 2
    img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    top    = int(round(dh - 0.1))
    bottom = int(round(dh + 0.1))
    left   = int(round(dw - 0.1))
    right  = int(round(dw + 0.1))
    img_padded = cv2.copyMakeBorder(
        img_resized, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=color
    )
    return img_padded, r, dw, dh


def xywh2xyxy(x):
    y = np.zeros_like(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def process(input, mask, anchors):
    anchors = [anchors[i] for i in mask]
    grid_h, grid_w = map(int, input.shape[0:2])
    box_confidence = np.expand_dims(input[..., 4], axis=-1)
    box_class_probs = input[..., 5:]
    box_xy = input[..., :2] * 2 - 0.5
    col = np.tile(np.arange(0, grid_w), grid_w).reshape(-1, grid_w)
    row = np.tile(np.arange(0, grid_h).reshape(-1, 1), grid_h)
    col = col.reshape(grid_h, grid_w, 1, 1).repeat(3, axis=-2)
    row = row.reshape(grid_h, grid_w, 1, 1).repeat(3, axis=-2)
    grid = np.concatenate((col, row), axis=-1)
    box_xy += grid
    box_xy *= int(IMG_SIZE / grid_h)
    box_wh = pow(input[..., 2:4] * 2, 2)
    box_wh = box_wh * anchors
    return np.concatenate((box_xy, box_wh), axis=-1), box_confidence, box_class_probs


def filter_boxes(boxes, box_confidences, box_class_probs):
    boxes = boxes.reshape(-1, 4)
    box_confidences = box_confidences.reshape(-1)
    box_class_probs = box_class_probs.reshape(-1, box_class_probs.shape[-1])
    _box_pos = np.where(box_confidences >= OBJ_THRESH)
    boxes = boxes[_box_pos]
    box_confidences = box_confidences[_box_pos]
    box_class_probs = box_class_probs[_box_pos]
    class_max_score = np.max(box_class_probs, axis=-1)
    classes = np.argmax(box_class_probs, axis=-1)
    _class_pos = np.where(class_max_score >= OBJ_THRESH)
    return boxes[_class_pos], classes[_class_pos], (class_max_score * box_confidences)[_class_pos]


def nms_boxes(boxes, scores):
    x = boxes[:, 0]
    y = boxes[:, 1]
    w = boxes[:, 2] - boxes[:, 0]
    h = boxes[:, 3] - boxes[:, 1]
    areas = w * h
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x[i], x[order[1:]])
        yy1 = np.maximum(y[i], y[order[1:]])
        xx2 = np.minimum(x[i] + w[i], x[order[1:]] + w[order[1:]])
        yy2 = np.minimum(y[i] + h[i], y[order[1:]] + h[order[1:]])
        w1 = np.maximum(0.0, xx2 - xx1 + 0.00001)
        h1 = np.maximum(0.0, yy2 - yy1 + 0.00001)
        inter = w1 * h1
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= NMS_THRESH)[0]
        order = order[inds + 1]
    return np.array(keep)


def postprocess_yolov5s(outputs, ratio, dw, dh, src_w, src_h):
    input_data = []
    for out in outputs:
        data = out.reshape([3, -1] + list(out.shape[-2:]))
        input_data.append(np.transpose(data, (2, 3, 0, 1)))

    boxes, classes, scores = [], [], []
    for input, mask in zip(input_data, MASKS):
        b, c, s = process(input, mask, ANCHORS)
        b, c, s = filter_boxes(b, c, s)
        boxes.append(b)
        classes.append(c)
        scores.append(s)

    if not boxes:
        return np.empty((0, 4), dtype=int), np.empty((0,)), np.empty((0,), dtype=int)

    boxes = np.concatenate(boxes)
    boxes = xywh2xyxy(boxes)
    classes = np.concatenate(classes)
    scores = np.concatenate(scores)

    nboxes, nclasses, nscores = [], [], []
    for c in set(classes.tolist()):
        inds = np.where(classes == c)
        b = boxes[inds]
        s = scores[inds]
        keep = nms_boxes(b, s)
        nboxes.append(b[keep])
        nclasses.append(classes[inds][keep])
        nscores.append(s[keep])
    if not nboxes:
        return np.empty((0, 4), dtype=int), np.empty((0,)), np.empty((0,), dtype=int)

    boxes = np.concatenate(nboxes)
    scores = np.concatenate(nscores)
    classes = np.concatenate(nclasses)

    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - dw) / ratio
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - dh) / ratio
    boxes[:, 0] = np.clip(boxes[:, 0], 0, src_w)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, src_h)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, src_w)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, src_h)
    return boxes.astype(np.int32), scores, classes.astype(np.int32)


def draw_results(img, boxes, scores, cls_ids):
    for box, score, cid in zip(boxes, scores, cls_ids):
        x1, y1, x2, y2 = box
        name  = CLASS_NAMES[cid] if cid < len(CLASS_NAMES) else str(cid)
        label = '{} {:.2f}'.format(name, score)
        np.random.seed(cid + 42)
        color = tuple(int(c) for c in np.random.randint(60, 255, 3))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(img, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(img, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    return img


class FPSCounter:
    def __init__(self, window=30):
        self.window = window
        self.times  = []
    def tick(self):
        self.times.append(time.time())
        if len(self.times) > self.window:
            self.times.pop(0)
    def fps(self):
        if len(self.times) < 2:
            return 0.0
        dt = self.times[-1] - self.times[0]
        return (len(self.times) - 1) / dt if dt > 0 else 0.0


def center_window(win_name, fw, fh):
    try:
        import tkinter
        _r = tkinter.Tk()
        _r.withdraw()
        sw, sh = _r.winfo_screenwidth(), _r.winfo_screenheight()
        _r.destroy()
    except Exception:
        sw, sh = 1920, 1080
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


def main():
    print('[INIT] 加载 RKNN 模型: {}'.format(MODEL_PATH))
    rknn = RKNNLite()
    ret = rknn.load_rknn(MODEL_PATH)
    if ret != 0:
        raise RuntimeError('load_rknn 失败: {}'.format(ret))
    ret = rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0)
    if ret != 0:
        raise RuntimeError('init_runtime 失败: {}'.format(ret))
    print('[INIT] NPU 双核初始化完成')

    print('[CAM] 打开 {} ...'.format(DEVICE))
    cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    if not cap.isOpened():
        raise RuntimeError('无法打开 {}，请检查连接'.format(DEVICE))
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print('[CAM] 分辨率: {}x{}'.format(actual_w, actual_h))

    fps_counter = FPSCounter(window=30)
    frame_index = 0
    win_moved = False
    print('[RUN] 开始推理，按 Ctrl+C 退出...\n')

    while True:
        ret, frame = cap.read()
        if not ret:
            print('[WARN] 取帧失败')
            time.sleep(0.01)
            continue
        src_h, src_w = frame.shape[:2]
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_lb, ratio, dw, dh = letterbox(img_rgb, IMG_SIZE)
        input_data = np.expand_dims(img_lb, axis=0)
        t1 = time.time()
        outputs = rknn.inference(inputs=[input_data])
        t2 = time.time()
        if outputs is None or outputs[0] is None:
            print('[ERR] 推理返回空结果')
            continue
        boxes, scores, cls_ids = postprocess_yolov5s(
            outputs, ratio, dw, dh, src_w, src_h
        )
        frame = draw_results(frame, boxes, scores, cls_ids)
        frame_index += 1
        if frame_index % SAVE_EVERY == 0:
            cv2.imwrite(SAVE_PATH, frame)
        try:
            cv2.imshow('MIPI + YOLOv5s Detection', frame)
            if not win_moved:
                win_moved = True
                center_window('MIPI + YOLOv5s Detection',
                              frame.shape[1], frame.shape[0])
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        except cv2.error:
            pass
        fps_counter.tick()
        fps_val = fps_counter.fps()
        info = 'YOLOv5s-Relu | NPU | {:.1f} FPS | det:{}'.format(fps_val, len(scores))
        cv2.putText(frame, info, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
        infer_ms = (t2 - t1) * 1000
        print('\r[FPS] {:.1f}  [NPU] {:.1f}ms  [DET] {} obj'.format(
            fps_val, infer_ms, len(scores)), end='', flush=True)
    cap.release()
    rknn.release()
    print('\n[EXIT] 已退出')

if __name__ == '__main__':
    main()
