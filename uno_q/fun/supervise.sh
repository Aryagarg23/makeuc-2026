#!/bin/sh
# On the UNO Q, started at boot by cron (@reboot), or by start_fun.sh with 'now': keeps fun_server.py running, restarting it within 2 s
# if it ever exits or crashes. Stop everything with: pkill -f gvs/supervise.sh; pkill -f '^python3 fun_server.py'
cd /home/arduino/gvs || exit 1
[ "${1:-}" = "now" ] || sleep 20   # at boot: let NetworkManager bring the hotspot up and BlueZ settle
while true; do
  for a in $(bluetoothctl devices Connected 2>/dev/null | awk '/GVS-zapper/{print $2}'); do
    bluetoothctl disconnect "$a" >/dev/null 2>&1
  done
  echo "$(date '+%F %T') starting fun_server" >> fun.log
  python3 fun_server.py < /dev/null >> fun.log 2>&1
  echo "$(date '+%F %T') fun_server exited ($?), restarting in 2 s" >> fun.log
  sleep 2
done
