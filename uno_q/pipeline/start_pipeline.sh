#!/bin/sh
# The packet pipeline and its rules dashboard, running on the UNO Q. Run on the Mac with the UNO Q on USB.
#
#   uno_q/pipeline/start_pipeline.sh demo              synthetic traffic made on the board, dry run (no stimuli)
#   uno_q/pipeline/start_pipeline.sh mac IFACE [MA]    the Mac's tshark on IFACE (e.g. en0) streams packet lines
#                                                      over USB to the board; with MA (mA at full strength, <= 2.0),
#                                                      confirmed windows stimulate through fun mode's Bluetooth link
#   uno_q/pipeline/start_pipeline.sh stop
#
# Dashboard: on the arya-gvs hotspot at http://10.42.0.1:8081/#key=KEY, and on this Mac at
# http://127.0.0.1:18081/#key=KEY (adb forward). The key lives in store/dashboard.key on the board and is
# printed below; without it the page shows nothing and changes nothing (friends share the hotspot).
# Why packets come from the Mac: the board has no tshark, no internet to install it, and capturing raw
# packets needs root there. The Mac's tshark needs capture permission (Wireshark's ChmodBPF, or sudo).
set -eu
cd "$(dirname "$0")"
ROOT=$(cd ../.. && pwd)
SER=$(adb devices | awk '$2=="device"{print $1; exit}')
[ -n "$SER" ] || { echo "UNO Q not found on adb"; exit 1; }
A="adb -s $SER"
D=/home/arduino/gvs/pipeline

$A shell "pkill -f '[g]vs_pipeline' ; pkill -f '[d]emo_feed.py' ; pkill -f '[r]un_pipeline.sh' ; true"
if [ "${1:-}" = "stop" ]; then adb -s "$SER" forward --remove tcp:18081 2>/dev/null || true; echo "pipeline stopped"; exit 0; fi

$A shell "mkdir -p $D/gvs_pipeline $D/tools $D/store"
for f in "$ROOT"/pipeline/gvs_pipeline/*.py "$ROOT/pipeline/gvs_pipeline/dashboard.html"; do
  $A push -q "$f" "$D/gvs_pipeline/"
done
$A push -q "$ROOT/pipeline/tools/demo_feed.py" "$D/tools/"
$A push -q run_pipeline.sh "$D/"
[ -f "$ROOT/pipeline/prototypes.json" ] && $A push -q "$ROOT/pipeline/prototypes.json" "$D/store/prototypes.json"
$A forward tcp:18081 tcp:8081 >/dev/null

show_key() {
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    K=$($A shell "cat $D/store/dashboard.key 2>/dev/null" | tr -d '\r\n')
    [ -n "$K" ] && break
    sleep 1
  done
  echo "dashboard: http://10.42.0.1:8081/#key=$K   (hotspot arya-gvs)"
  echo "           http://127.0.0.1:18081/#key=$K   (this Mac, over USB)"
}

case "${1:-demo}" in
  demo)
    $A shell "setsid nohup sh $D/run_pipeline.sh demo < /dev/null > /dev/null 2>&1 &"
    show_key ;;
  mac)
    IFACE="${2:?usage: start_pipeline.sh mac IFACE [MA]}"
    MA="${3:-}"
    (sleep 3; show_key) &
    "$ROOT/uno_q/linux/capture.sh" "$IFACE" | $A shell "sh $D/run_pipeline.sh stdin $MA" ;;
  *) echo "usage: start_pipeline.sh demo | mac IFACE [MA] | stop"; exit 2 ;;
esac
