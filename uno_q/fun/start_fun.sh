#!/bin/sh
# Fun mode: the UNO Q runs WiFi hotspot "arya-gvs" (password CHANGE_ME_hotspot) and serves the steering page at
# http://10.42.0.1:8080/, driving the GVS board over Bluetooth itself. Run on the Mac with the UNO Q on USB.
#
#   uno_q/fun/start_fun.sh          start (or restart) fun mode
#   uno_q/fun/start_fun.sh stop     stop the UNO Q server and hotspot
#
# The board's Bluetooth takes one connection at a time, so this stops the Mac's BLE relay first
# (gvs/tools/ble_bridge.py); start that again for pipeline mode. There is no Mac-charger check: keep the Mac
# off its charger whenever the GVS board is on USB with pads on (the page warns while the board is on USB).
set -eu
cd "$(dirname "$0")"
ROOT=$(cd ../.. && pwd)
SER=$(adb devices | awk '$2=="device"{print $1; exit}')
[ -n "$SER" ] || { echo "UNO Q not found on adb"; exit 1; }
A="adb -s $SER"
D=/home/arduino/gvs

stop_all() {
  $A shell "pkill -f '[g]vs/supervise.sh'; pkill -f '^python3 fun_server.py'; nmcli con down Hotspot >/dev/null 2>&1; true"
}

if [ "${1:-}" = "stop" ]; then stop_all; echo "fun mode stopped"; exit 0; fi

pkill -f gvs/tools/ble_bridge.py 2>/dev/null && echo "stopped the Mac BLE relay (one Bluetooth connection at a time)" || true
stop_all

$A shell "mkdir -p $D/lib"
$A push -q fun_server.py "$D/fun_server.py"
$A push -q supervise.sh "$D/supervise.sh"
$A push -q "$ROOT/gvs/tools/live.html" "$D/live.html"
grep '^GVS_TOKEN=' "$ROOT/gvs/device.env" | cut -d= -f2 | $A shell "cat > $D/token"
if ! $A shell "test -d $D/lib/bleak"; then
  for w in wheels/*.whl; do
    $A push -q "$w" "$D/"
    $A shell "cd $D && python3 -m zipfile -e $(basename "$w") lib/ && rm $(basename "$w")"
  done
fi

$A shell "nmcli dev wifi hotspot ifname wlan0 ssid arya-gvs password CHANGE_ME_hotspot band bg >/dev/null && nmcli -t -f IP4.ADDRESS dev show wlan0"


# The supervisor keeps fun_server.py running (restart within 2 s if it dies); cron starts it at boot too.
$A shell "setsid nohup sh $D/supervise.sh now < /dev/null > $D/boot.log 2>&1 &"
sleep 12
$A shell "tail -3 $D/fun.log"
$A forward tcp:8080 tcp:8080 >/dev/null
echo "fun mode: join WiFi 'arya-gvs' (password CHANGE_ME_hotspot) and open http://10.42.0.1:8080/"
echo "          or on this Mac: http://127.0.0.1:8080/"
