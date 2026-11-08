#!/usr/bin/env python3
"""Check a GVSLOG card layout. Usage: verify_sd.py /Volumes/GVSLOG"""
import json, sys, os

HEADER = "uptime_ms,bucket,intensity,duty,ms,result,reason"
errors = []

def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        errors.append(msg)

def main(root):
    cfg_path = os.path.join(root, "config.json")
    cfg = None
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        check(isinstance(cfg, dict), "config.json parses to an object")
    except Exception as e:
        check(False, f"config.json parses ({e})")
    if isinstance(cfg, dict):
        for key, typ in (("device_name", str), ("wifi_ssid", str), ("wifi_password", str)):
            check(isinstance(cfg.get(key), typ), f"{key} is a string")
        d = cfg.get("max_duty")
        is_num = isinstance(d, (int, float)) and not isinstance(d, bool)
        check(is_num, "max_duty is a number")
        check(is_num and 0 < d <= 0.6, f"max_duty in (0, 0.6] (got {d!r})")
    try:
        with open(os.path.join(root, "log", "trials.csv")) as f:
            first = f.readline().rstrip("\r\n")
        check(first == HEADER, "log/trials.csv first line equals header")
    except Exception as e:
        check(False, f"log/trials.csv readable ({e})")
    print("RESULT:", "FAIL" if errors else "PASS")
    return 1 if errors else 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: verify_sd.py MOUNT_PATH")
    sys.exit(main(sys.argv[1]))
