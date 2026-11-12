#!/bin/sh
# Native game only; the user's model remains independently managed.
set -eu
cd "$(dirname "$0")"
exec taskset -c 0-3 nice -n 10 ionice -c 3 python3 launch.py --build build-arm64 "$@"
