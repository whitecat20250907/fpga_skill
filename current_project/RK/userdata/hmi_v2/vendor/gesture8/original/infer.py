"""8 类手势轨迹推理 demo。

交互流程（单只手完成）
--------------------
    1. 握拳           → 待命（ARMED）
    2. 换成向上指      → 开始记录食指指尖轨迹（REC）
    3. 画完再握拳      → 结束记录，把轨迹转成 28x28 图送入分类器
    4. 显示结果        → 冷却后回到待命

状态机
------
    IDLE  --(握拳确认)-->  ARMED  --(向上指确认)-->  REC  --(再次握拳确认)-->  RESULT
      ^                      |                        |                          |
      |                (超时没向上指)            (手丢失/超时)              (冷却结束)
      +----------------------+------------------------+--------------------------+

用法
----
    python infer.py                 # 打开摄像头跑完整流程
    python infer.py --selftest      # 不接摄像头，用数据集图片验证权重与预处理
    python infer.py --camera 1      # 换摄像头
"""

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

import mediapipe as mp

# ============ 路径 ============
ROOT = Path(__file__).resolve().parent
GESTURE_MODEL_PATH = ROOT / "gesture_recognizer.task"
WEIGHTS_PATH = ROOT / "gesture_8class.pth"
CLASSES_JSON = ROOT / "gesture_classes.json"

# ============ 与采集/训练一致 ============
IMG_SIZE = 28
LINE_WIDTH = 1
INDEX_TIP_ID = 8              # 食指指尖

# ============ 手势类别（MediaPipe GestureRecognizer 自带） ============
FIST_GESTURE = "Closed_Fist"
POINT_GESTURE = "Pointing_Up"
GESTURE_SCORE_TH = 0.50

# ============ 状态机参数 ============
ARM_FRAMES = 3               # 连续 N 帧握拳 → 进入待命
POINT_CONFIRM_FRAMES = 2     # 连续 N 帧向上指 → 开始记录
END_FIST_FRAMES = 3          # 连续 N 帧握拳 → 结束记录
ARM_TIMEOUT_SEC = 4.0        # 待命后多久没向上指就放弃
MAX_RECORD_SEC = 10.0        # 单次记录上限
HAND_LOST_SEC = 1.0          # 记录中手丢失容忍时间
COOLDOWN_SEC = 1.2
MIN_POINTS = 5
POINT_MIN_DIST = 4           # 轨迹点最小间距（像素）
CONF_THRESHOLD = 0.60        # 分类置信度阈值

S_IDLE, S_ARMED, S_REC, S_RESULT = 0, 1, 2, 3
STATE_NAMES = {S_IDLE: "IDLE", S_ARMED: "ARMED (fist)",
               S_REC: "REC (point up)", S_RESULT: "RESULT"}


# ============ 模型（必须与 train.py 完全一致） ============
class GestureNet(nn.Module):
    """3 层卷积 + 全局平均池化 + 小分类头。输入 1x28x28。"""

    def __init__(self, num_classes=8, dropout=0.3):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(),
            nn.MaxPool2d(2),                                  # 28 -> 14
            nn.Conv2d(16, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(),
            nn.MaxPool2d(2),                                  # 14 -> 7
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(16, num_classes),
        )

    def forward(self, x):
        return self.classifier(self.features(x))


# ============ 轨迹转 28x28（与 collect.py 逐行一致） ============
def trajectory_to_image(points, size=IMG_SIZE, line_width=LINE_WIDTH):
    canvas = np.zeros((size, size), dtype=np.uint8)
    if len(points) < 2:
        return canvas

    pts = np.array(points, dtype=np.float32)

    x_min, y_min = pts.min(axis=0)
    x_max, y_max = pts.max(axis=0)
    w = x_max - x_min
    h = y_max - y_min
    s = max(w, h)

    if s < 1e-3:
        return canvas

    pts[:, 0] = (pts[:, 0] - x_min) / s
    pts[:, 1] = (pts[:, 1] - y_min) / s

    pad = line_width + 1
    usable = size - 2 * pad
    pts = pts * usable + pad
    pts = np.round(pts).astype(np.int32)

    for i in range(1, len(pts)):
        cv2.line(canvas, tuple(pts[i - 1]), tuple(pts[i]),
                 255, line_width, lineType=cv2.LINE_8)

    return canvas


# ============ 模型加载 ============
def load_classifier(weights_path, classes_path):
    if classes_path.is_file():
        meta = json.loads(classes_path.read_text(encoding="utf-8"))
        class_names = meta["class_names"]
        class_dirs = meta.get("class_dirs", [f"gesture_{n}" for n in class_names])
    else:
        class_names = ["0", "L", "L_rev", "L_up", "L_rev_up", "M", "W", "Z"]
        class_dirs = ["gesture_0", "gesture_L", "gesture_L_flipped",
                      "gesture_L_up", "gesture_L_flipped_up",
                      "gesture_M", "gesture_W", "gesture_Z"]
        print(f"[警告] 找不到 {classes_path.name}，使用内置类别顺序")

    model = GestureNet(num_classes=len(class_names))
    model.load_state_dict(torch.load(weights_path, map_location="cpu",
                                     weights_only=True))
    model.eval()
    return model, class_names, class_dirs


def predict(model, class_names, img_28):
    x = img_28.astype(np.float32) / 255.0
    x = torch.from_numpy(x).unsqueeze(0).unsqueeze(0)      # 1x1x28x28
    with torch.no_grad():
        probs = torch.softmax(model(x), dim=1)[0].numpy()
    idx = int(probs.argmax())
    return class_names[idx], float(probs[idx]), probs


# ============ MediaPipe ============
def build_recognizer():
    options = mp.tasks.vision.GestureRecognizerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(GESTURE_MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
    )
    return mp.tasks.vision.GestureRecognizer.create_from_options(options)


def top_gesture(result, hand_idx):
    """返回某只手的 (手势名, 分数)。"""
    if hand_idx < len(result.gestures) and result.gestures[hand_idx]:
        g = result.gestures[hand_idx][0]
        return g.category_name, float(g.score)
    return None, 0.0


def find_gesture_hand(result, want, score_th=GESTURE_SCORE_TH):
    """找出手势为 want 且分数最高的一只手，返回 (索引, 分数)。"""
    best_idx, best_score = None, 0.0
    for i in range(len(result.hand_landmarks)):
        name, score = top_gesture(result, i)
        if name == want and score >= score_th and score > best_score:
            best_idx, best_score = i, score
    return best_idx, best_score


def pick_active_hand(result, last_tip_px, w, h):
    """记录阶段挑出"正在画的那只手"。

    优先用当前被识别为向上指的手；一旦它变回拳头（手势不再是 Pointing_Up），
    就退化成"离最后一次轨迹点最近的那只手"，保证能持续跟踪同一只手。
    """
    idx, _ = find_gesture_hand(result, POINT_GESTURE)
    if idx is not None:
        return idx

    if last_tip_px is None or not result.hand_landmarks:
        return None

    best_idx, best_d = None, 1e9
    for i, hand in enumerate(result.hand_landmarks):
        lm = hand[INDEX_TIP_ID]
        px, py = lm.x * w, lm.y * h
        d = math.hypot(px - last_tip_px[0], py - last_tip_px[1])
        if d < best_d:
            best_idx, best_d = i, d
    return best_idx


# ============ 自检：不接摄像头验证权重 + 预处理 ============
def selftest(model, class_names, class_dirs, per_class=5):
    print("=" * 58)
    print("自检：用数据集图片验证权重与预处理（无摄像头）")
    print("=" * 58)

    correct, total = 0, 0
    for label, (name, dname) in enumerate(zip(class_names, class_dirs)):
        d = ROOT / dname
        if not d.is_dir():
            print(f"  {name:<10} 跳过（找不到 {dname}）")
            continue

        files = sorted(d.glob("*.png"))[:per_class]
        hits = 0
        for p in files:
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            pred, conf, _ = predict(model, class_names, img)
            hits += int(pred == name)
            total += 1
        correct += hits
        print(f"  {name:<10} {hits}/{len(files)}")

    print("-" * 58)
    print(f"合计 {correct}/{total} = {correct / max(1, total):.3f}")
    print("若这个数字很低，说明预处理或类别顺序与训练不一致。")


# ============ 主流程 ============
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--weights", type=Path, default=WEIGHTS_PATH)
    parser.add_argument("--classes", type=Path, default=CLASSES_JSON)
    parser.add_argument("--selftest", action="store_true",
                        help="不接摄像头，用数据集图片验证权重")
    parser.add_argument("--per-class", type=int, default=5,
                        help="自检时每类取几张")
    args = parser.parse_args()

    if not GESTURE_MODEL_PATH.is_file():
        raise FileNotFoundError(f"找不到手势模型：{GESTURE_MODEL_PATH}")
    if not args.weights.is_file():
        raise FileNotFoundError(
            f"找不到权重：{args.weights}\n请先运行 python train.py 生成。")

    model, class_names, class_dirs = load_classifier(args.weights, args.classes)
    print(f"已加载权重 {args.weights.name}，类别：{class_names}")

    if args.selftest:
        selftest(model, class_names, class_dirs, args.per_class)
        return

    recognizer = build_recognizer()

    camera = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        raise RuntimeError("无法打开摄像头")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # ---- 状态 ----
    state = S_IDLE
    arm_count = 0
    point_count = 0
    end_count = 0
    lost_since = None
    trajectory = []
    last_tip_px = None
    state_since = time.monotonic()
    result_text = ""
    result_detail = ""
    last_probs = None
    last_timestamp_ms = 0
    fps_buf = []

    print("=" * 58)
    print("手势轨迹推理 demo")
    print("=" * 58)
    print("  1) 握拳          → 待命")
    print("  2) 换成向上指     → 开始记录食指轨迹")
    print("  3) 画完再握拳     → 结束并分类")
    print("  q / ESC           → 退出")
    print("=" * 58)

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break

            t0 = time.monotonic()
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            ts_ms = time.monotonic_ns() // 1_000_000
            if ts_ms <= last_timestamp_ms:
                ts_ms = last_timestamp_ms + 1
            last_timestamp_ms = ts_ms

            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = recognizer.recognize_for_video(mp_img, ts_ms)

            now = time.monotonic()
            elapsed = now - state_since
            has_hand = len(result.hand_landmarks) > 0

            fist_idx, fist_score = find_gesture_hand(result, FIST_GESTURE)
            point_idx, point_score = find_gesture_hand(result, POINT_GESTURE)

            # ---------- 状态机 ----------
            if state == S_IDLE:
                arm_count = arm_count + 1 if fist_idx is not None else 0
                if arm_count >= ARM_FRAMES:
                    state, state_since = S_ARMED, now
                    arm_count = point_count = end_count = 0
                    trajectory, last_tip_px = [], None
                    print("[待命] 检测到握拳，请换成向上指")

            elif state == S_ARMED:
                point_count = point_count + 1 if point_idx is not None else 0
                if point_count >= POINT_CONFIRM_FRAMES:
                    state, state_since = S_REC, now
                    trajectory, last_tip_px = [], None
                    end_count = 0
                    lost_since = None
                    print("[记录] 向上指确认，开始采集轨迹")
                elif elapsed > ARM_TIMEOUT_SEC:
                    state, state_since = S_IDLE, now
                    arm_count = 0
                    print("[超时] 待命期间没检测到向上指，回到空闲")

            elif state == S_REC:
                active = pick_active_hand(result, last_tip_px, w, h)

                if active is None or not has_hand:
                    # 手暂时丢失：给一点容忍时间，超时才放弃
                    if lost_since is None:
                        lost_since = now
                    if now - lost_since > HAND_LOST_SEC:
                        state, state_since = S_IDLE, now
                        lost_since = None
                        print("[丢弃] 记录中手丢失，回到空闲")
                else:
                    lost_since = None
                    name, score = top_gesture(result, active)

                    is_fist = (name == FIST_GESTURE and score >= GESTURE_SCORE_TH)
                    end_count = end_count + 1 if is_fist else 0

                    if not is_fist:
                        lm = result.hand_landmarks[active][INDEX_TIP_ID]
                        tip = (int(lm.x * w), int(lm.y * h))
                        if (not trajectory) or math.hypot(
                                tip[0] - trajectory[-1][0],
                                tip[1] - trajectory[-1][1]) > POINT_MIN_DIST:
                            trajectory.append(tip)
                        last_tip_px = tip

                    if end_count >= END_FIST_FRAMES:
                        n = len(trajectory)
                        print(f"[结束] 再次握拳，轨迹 {n} 点")

                        if n < MIN_POINTS:
                            result_text = f"轨迹太短 ({n} 点)"
                            result_detail = ""
                            last_probs = None
                            print(f"[丢弃] {result_text}")
                        else:
                            img = trajectory_to_image(trajectory)
                            nonzero = int((img > 0).sum())
                            if nonzero < 3:
                                result_text = "轨迹几乎空白"
                                result_detail = ""
                                last_probs = None
                                print(f"[丢弃] {result_text}")
                            else:
                                label, conf, probs = predict(model, class_names, img)
                                top3 = np.argsort(probs)[::-1][:3]
                                detail = "  ".join(
                                    f"{class_names[i]}={probs[i]:.2f}" for i in top3)
                                if conf >= CONF_THRESHOLD:
                                    result_text = f"{label}  ({conf:.2f})"
                                    print(f"[识别] {label}  conf={conf:.2f}  [{detail}]")
                                else:
                                    result_text = f"置信度低 ({conf:.2f})"
                                    print(f"[忽略] {result_text}  候选[{detail}]")
                                result_detail = detail
                                last_probs = probs
                                cv2.imwrite(str(ROOT / "last_trajectory.png"),
                                            cv2.resize(img, (280, 280),
                                                       interpolation=cv2.INTER_NEAREST))

                        state, state_since = S_RESULT, now
                        end_count = 0

                    elif (now - state_since) > MAX_RECORD_SEC:
                        state, state_since = S_IDLE, now
                        print("[超时] 记录超过上限，丢弃")

            elif state == S_RESULT:
                if elapsed > COOLDOWN_SEC:
                    state, state_since = S_IDLE, now
                    arm_count = point_count = end_count = 0
                    trajectory, last_tip_px = [], None

            # ---------- 绘制 ----------
            for i, hand in enumerate(result.hand_landmarks):
                for j, lm in enumerate(hand):
                    p = (int(lm.x * w), int(lm.y * h))
                    if j == INDEX_TIP_ID:
                        cv2.circle(frame, p, 7, (0, 0, 255), -1)
                    else:
                        cv2.circle(frame, p, 2, (0, 200, 0), -1)

            if state == S_REC and len(trajectory) > 1:
                for i in range(1, len(trajectory)):
                    cv2.line(frame, trajectory[i - 1], trajectory[i],
                             (255, 200, 0), 3)

            state_color = {S_IDLE: (170, 170, 170), S_ARMED: (0, 200, 255),
                           S_REC: (0, 0, 255), S_RESULT: (0, 255, 0)}[state]
            cv2.putText(frame, f"State: {STATE_NAMES[state]}", (16, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, state_color, 2)
            cv2.putText(frame, f"Points: {len(trajectory)}", (16, 66),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

            y = 96
            for i in range(len(result.hand_landmarks)):
                name, score = top_gesture(result, i)
                if name:
                    cv2.putText(frame, f"Hand{i}: {name} {score:.2f}", (16, y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    y += 22

            if state == S_REC and len(trajectory) >= 2:
                thumb = trajectory_to_image(trajectory)
                big = cv2.resize(thumb, (140, 140), interpolation=cv2.INTER_NEAREST)
                frame[h - 160:h - 20, w - 160:w - 20] = cv2.cvtColor(
                    big, cv2.COLOR_GRAY2BGR)
                cv2.rectangle(frame, (w - 160, h - 160), (w - 20, h - 20),
                              (0, 255, 0), 2)

            if state == S_RESULT and result_text:
                cv2.putText(frame, result_text, (16, h - 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                if result_detail:
                    cv2.putText(frame, result_detail, (16, h - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                (200, 200, 200), 1)

            dt = time.monotonic() - t0
            if dt > 0:
                fps_buf.append(1.0 / dt)
                if len(fps_buf) > 30:
                    fps_buf.pop(0)
            if fps_buf:
                cv2.putText(frame, f"FPS: {np.mean(fps_buf):.1f}",
                            (w - 130, 28), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (0, 255, 0), 1)

            cv2.imshow("Gesture Infer - 8 class", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        recognizer.close()


if __name__ == "__main__":
    main()
