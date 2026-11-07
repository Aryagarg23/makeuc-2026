GVSLOG: microSD for the ESP32 GVS data logger (FAT32, MBR).
config.json keys: device_name (string), max_duty (number, 0 < x <= 0.6; may only lower the firmware ceiling),
wifi_ssid (string, empty = serial-only mode), wifi_password (string).
log/trials.csv is appended by the firmware: uptime_ms,bucket,intensity,duty,ms,result,reason
