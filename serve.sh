#!/bin/sh
# Serve this repository over plain HTTP for the kernel's `pkg` installer.
# QEMU's user-mode network makes the host reachable as 10.0.2.2.
set -eu
cd "$(dirname "$0")"
exec python3 -m http.server "${PORT:-8000}"
