#!/bin/sh
# Opt-in hand module; observation only unless --send-actions is supplied.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
prefix="$PWD/.gesture-v1"
python="${NPU_PYTHON:-/userdata/gaze_model_migration_v1_20261014/app_venv/bin/python}"
if [ ! -x "$python" ]; then
    echo 'RKNN runtime environment is absent; see GESTURE_RK3576.md.' >&2
    exit 1
fi
mkdir -p logs
output="logs/gesture-$(date +%Y%m%d_%H%M%S)-$$"
exec env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 taskset -c "${GESTURE_CPU:-0-7}" nice -n 10 ionice -c 3 \
    "$python" -B tools/run_mediapipe_gestures.py \
    --app-dir "${APP_DIR:-/userdata/gaze_model_migration_v1_20261014/app_v34_cpu_reuse_20261022}" \
    --fps "${GESTURE_FPS:-0}" --output "$output" "$@"
