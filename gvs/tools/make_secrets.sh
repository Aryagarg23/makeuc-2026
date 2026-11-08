#!/bin/sh
# Writes gvs/firmware/gvs_controller/secrets.h with a random TOKEN and AP_PASS, and
# gvs/device.env (GVS_URL, GVS_TOKEN) for the pipeline. Refuses to overwrite either.
# Usage: make_secrets.sh [WIFI_SSID WIFI_PASS]
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
h="$here/firmware/gvs_controller/secrets.h"; env="$here/device.env"
for f in "$h" "$env"; do [ -e "$f" ] && { echo "exists: $f" >&2; exit 1; }; done
tok=$(openssl rand -hex 12); ap=$(openssl rand -hex 6)
umask 077
cat > "$h" <<H
#pragma once
const char* WIFI_SSID = "${1:-}";
const char* WIFI_PASS = "${2:-}";
const char* TOKEN     = "$tok";
const char* AP_PASS   = "$ap";
H
url=http://192.168.4.1; [ -n "${1:-}" ] && url=http://gvs.local
printf 'GVS_URL=%s\nGVS_TOKEN=%s\nGVS_AP_PASS=%s\n' "$url" "$tok" "$ap" > "$env"
echo "wrote $h and $env"
