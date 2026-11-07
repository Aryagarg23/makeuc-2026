#!/usr/bin/env bash
set -euo pipefail
mkdir -p ~/tribev2/work && cd ~/tribev2/work
~/tribev2/.venv/bin/python - <<'PY'
from gtts import gTTS
gTTS("Hello. This is a short test clip for the brain encoding model. "
     "A red square moves across the screen while I keep talking about reels and messages.", lang="en").save("speech.mp3")
print("tts ok")
PY
ffmpeg -y -loglevel error -f lavfi -i testsrc2=size=640x360:rate=30:duration=12 -i speech.mp3 \
  -filter_complex "[1:a]apad=whole_dur=12[a]" -map 0:v -map "[a]" -c:v libx264 -pix_fmt yuv420p -c:a aac -t 12 test12.mp4
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height -of compact test12.mp4
