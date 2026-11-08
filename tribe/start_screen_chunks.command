#!/bin/sh
# Double-click: records the Mac screen + mic in 10 s chunks and sends them to TRIBE (needs the
# ssh tunnel to the GPU box: ssh -N -L 8770:127.0.0.1:8770 wsl). Terminal asks for Screen Recording once.
cd "$(dirname "$0")/.." && exec pipeline/.venv/bin/python tribe/screen_chunks.py
