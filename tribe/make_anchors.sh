#!/usr/bin/env bash
# The two fixed anchor clips every bucket's TRIBE score is placed between (research/tribe_v2.md, Recommendation).
#   neutral: 60 s of one still frame with silent audio. Pass an iPhone home-screen screenshot as $1;
#            without one, a plain #1c1c1e frame is used (CHOSE: dark grey, iOS dark-mode background).
#   high:    the Sintel trailer the official TRIBE demo notebook uses.
set -euo pipefail
mkdir -p ~/tribev2/anchors && cd ~/tribev2/anchors
if [ "${1:-}" ]; then
  ffmpeg -y -loglevel error -loop 1 -i "$1" -f lavfi -i anullsrc=r=16000:cl=mono -t 60 \
    -vf "scale=720:-2,format=yuv420p" -c:v libx264 -c:a aac -shortest neutral.mp4
else
  ffmpeg -y -loglevel error -f lavfi -i color=c=0x1c1c1e:s=720x1280:r=30 -f lavfi -i anullsrc=r=16000:cl=mono -t 60 \
    -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest neutral.mp4
fi
[ -f sintel.mp4 ] || curl -fsSL -o sintel.mp4 https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 neutral.mp4 sintel.mp4
