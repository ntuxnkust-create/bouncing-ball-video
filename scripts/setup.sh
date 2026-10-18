#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v python3 >/dev/null
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg (with libx264 and AAC) first.' >&2; exit 1; }
command -v ffprobe >/dev/null
python3 -m venv .venv
.venv/bin/python -m pip install --cache-dir /tmp/bouncing-ball-pip-cache -r requirements.txt
.venv/bin/python -m pip check
