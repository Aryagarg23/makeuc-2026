#!/usr/bin/env python3
"""Hardware check for gvs_controller. Usage: serial_check.py [port]"""
import json, sys, time, serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem1101"
ser = serial.Serial(PORT, 115200, timeout=3)
ser.dtr = False; ser.rts = False
time.sleep(0.3); ser.reset_input_buffer()

def send(raw):
    ser.write((raw if isinstance(raw, str) else json.dumps(raw)).encode() + b"\n")
    line = ser.readline().decode().strip()
    print(f"> {raw if isinstance(raw, str) else json.dumps(raw)}\n< {line}")
    return json.loads(line)

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: sys.exit(1)

MAXD = int(0.4 * 1023 + 0.5)
s = send({"cmd": "status"})
check("status fields", all(k in s for k in
      ["chip","uptime_ms","armed","sd","max_duty","stims_last_hour","last_stim_ms_ago","estop"]))
check("boot disarmed", s["armed"] is False)
check("stim before arm refused", send({"cmd":"stim","bucket":"t","intensity":0.5,"ms":500}) ==
      {"ok": False, "reason": "not_armed"})
check("arm ok", send({"cmd":"arm"})["armed"] is True)
r = send({"cmd":"stim","bucket":"t","intensity":2.0,"ms":99999})
check("clamped accept", r["ok"] and r["ms"] == 2000 and r["duty"] <= MAXD and r["intensity"] == 1.0)
r = send({"cmd":"stim","bucket":"t","intensity":0.5,"ms":100})
check("second stim refused (busy or cooldown)", r["ok"] is False and r["reason"] in ("busy","cooldown"))
check("stop ok", send({"cmd":"stop"})["ok"] is True)
check("status after stop: inactive", send({"cmd":"status"})["active"] is False)
r = send({"cmd":"stim","bucket":"t","intensity":0.5,"ms":100})
check("within 5 s of previous end: cooldown", r == {"ok": False, "reason": "cooldown"})
check("malformed -> parse", send("{not json") == {"ok": False, "reason": "parse"})
check("hourly count", send({"cmd":"status"})["stims_last_hour"] == 1)
print("waiting 5.2 s for cooldown...")
time.sleep(5.2)
r = send({"cmd":"stim","bucket":"t","intensity":0.25,"ms":10})
check("after cooldown accepted, ms clamped up to 50", r["ok"] and r["ms"] == 50)
send({"cmd":"disarm"})
check("disarmed", send({"cmd":"status"})["armed"] is False)
print("ALL CHECKS PASSED")
