#!/bin/sh
# Native ARM64 build on Debian 12 / Ubuntu with an X11 desktop.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
case "$(uname -m)" in aarch64|arm64) ;; *) echo 'This script expects ARM64 Linux.'; exit 1;; esac
jobs=${JOBS:-1}
case "$jobs" in ''|*[!0-9]*|0) echo 'JOBS must be a positive integer.'; exit 1;; esac
if [ "${SKIP_APT:-0}" != 1 ]; then
if [ "$(id -u)" = 0 ]; then SUDO=; else SUDO=sudo; fi
curl_dev=libcurl4-gnutls-dev
# Keep an existing curl development flavour: replacing it can remove unrelated
# development packages on an SDK image. Never allow package removals here.
if dpkg-query -W -f='${Status}' libcurl4-openssl-dev 2>/dev/null | grep -q 'install ok installed'; then
  curl_dev=libcurl4-openssl-dev
fi
$SUDO apt-get update
$SUDO apt-get install -y --no-remove --no-install-recommends build-essential meson ninja-build pkg-config python3 \
  libgtk-3-dev libicu-dev "$curl_dev" libsqlite3-dev liblzma-dev \
  libzstd-dev zlib1g-dev libbz2-dev fonts-noto-cjk python3-gi python3-gi-cairo
fi
reconfigure=
if [ -f build-arm64/meson-private/coredata.dat ]; then reconfigure=--reconfigure; fi
meson setup $reconfigure build-arm64 upstream/freeciv-3.2.6 --buildtype=release \
  -Dclients=gtk3.22 -Dfcmp=[] -Dtools=[] -Daudio=none -Dmwand=false \
  -Dreadline=false -Dsyslua=false -Dsvgflags=false -Dnls=false
# Default to one job to reduce peak memory on a 2 GB development board.
ninja -C build-arm64 -j "$jobs"
echo 'Build complete. Run: python3 launch.py --build build-arm64'
