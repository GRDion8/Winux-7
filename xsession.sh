#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
openbox &
wm_pid=$!
trap 'kill "$wm_pid" 2>/dev/null || true' EXIT
python setup.py --install
