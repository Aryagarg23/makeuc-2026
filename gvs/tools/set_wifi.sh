#!/bin/sh
# Put WiFi credentials into secrets.h (git-ignored) without them passing through anyone else.
# Prompts for SSID and password (password not echoed), keeps the existing TOKEN and AP_PASS,
# and points device.env at http://gvs.local. The ESP32-C3 only joins 2.4 GHz networks.
# Usage: gvs/tools/set_wifi.sh   then reflash.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
h="$here/firmware/gvs_controller/secrets.h"; env="$here/device.env"
[ -f "$h" ] && [ -f "$env" ] || { echo "run make_secrets.sh first" >&2; exit 1; }
printf 'WiFi name (SSID): '; read -r ssid
printf 'WiFi password: '; stty -echo; read -r pass; stty echo; echo
case "$ssid$pass" in *\"*|*\\*) echo "quotes and backslashes aren't supported here; edit secrets.h by hand" >&2; exit 1;; esac
tmp=$(mktemp)
sed -e "s|^const char\* WIFI_SSID = .*|const char* WIFI_SSID = \"$ssid\";|" \
    -e "s|^const char\* WIFI_PASS = .*|const char* WIFI_PASS = \"$pass\";|" "$h" > "$tmp"
cat "$tmp" > "$h"; rm -f "$tmp"
sed -i '' -e 's|^GVS_URL=.*|GVS_URL=http://gvs.local|' "$env"
echo "secrets.h updated for '$ssid'; device.env -> http://gvs.local. Now reflash."
