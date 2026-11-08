#!/bin/sh
# On the UNO Q: run the packet pipeline with its rules dashboard on the hotspot (port 8081, key required).
#   run_pipeline.sh demo               synthetic traffic made on the board (tools/demo_feed.py), dry run
#   run_pipeline.sh stdin [MAX_MA]     packet lines on stdin (the Mac's tshark, streamed over adb); with MAX_MA,
#                                      confirmed windows stimulate through fun mode's Bluetooth link (fun_server.py :8080)
cd /home/arduino/gvs/pipeline || exit 1
mkdir -p store
MODE="${1:-demo}"
ARGS="--store store/prototypes.json --window 3 live --dashboard 8081 --dashboard-host 0.0.0.0"
if [ "$MODE" = "demo" ]; then
  exec sh -c "python3 tools/demo_feed.py | python3 -m gvs_pipeline $ARGS" >> pipeline.log 2>&1
fi
if [ -n "${2:-}" ]; then
  ARGS="$ARGS --relay http://127.0.0.1:8080 --max-ma $2"
fi
exec python3 -m gvs_pipeline $ARGS 2>> pipeline.log
