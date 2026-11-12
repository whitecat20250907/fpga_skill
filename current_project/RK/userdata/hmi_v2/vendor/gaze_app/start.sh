#!/bin/sh
export GAZE_APP_DIR="/userdata/gaze_model_migration_v1_20261014/app_v51_native_export_20261024"
export NPU_MAX_FACES="${NPU_MAX_FACES:-2}"
set -eu
export NPU_REQUIRE_FPGA_DETECTOR=1
[ -n "${FPGA_MODEL_FDS:-}" ] || { echo "FPGA model DMA/BAR descriptors must be supplied by the owned launcher" >&2; exit 2; }
cd "$(dirname "$0")"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/linaro/.Xauthority}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
exec /userdata/gaze_model_migration_v1_20261014/app_venv/bin/python run_gaze.py "$@"
