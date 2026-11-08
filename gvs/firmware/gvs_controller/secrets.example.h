// Copy to secrets.h (git-ignored) and fill in. tools/make_secrets.sh writes one with a random token.
#pragma once
const char* WIFI_SSID = "";          // empty: skip straight to the GVS-zapper hotspot
const char* WIFI_PASS = "";
const char* TOKEN     = "change-me"; // /pulse /stop /status /boost need ?token=
const char* AP_PASS   = "zapzap123"; // GVS-zapper hotspot password, >= 8 chars
