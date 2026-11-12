#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec /userdata/gaze_model_migration_v1_20261014/app_venv/bin/python -B run_gesture8.py "$@"
