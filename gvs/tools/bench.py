"""Bench tests for the GVS device over USB serial. NO PERSON ATTACHED for any of these.

  python bench.py status
  python bench.py idle                      # unpowered or powered: output off, relays released, no fault
  python bench.py power                     # after the battery feed wire: HV rail at battery voltage
  python bench.py boost-sweep --target 22   # steps boost duty until HV reaches target; boost off after
  python bench.py boostpct 18               # use 18% for pulses until reset (put it in BOOST_PCT to keep)
  python bench.py pulse 1.0 2000 --mode dc  # one pulse, status polled every 50 ms, trace + summary
  python bench.py limits                    # clamp, max duration, cooldown, stop

Each check prints PASS/FAIL with the numbers it judged; exit status 1 if any FAIL.
Uses the firmware's own readback (meas_ma, hv). Confirm with a meter across the dummy load:
volts / kΩ = mA.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import serial

PORT = "/dev/cu.usbmodem1101"
FAILS: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("PASS " if ok else "FAIL ") + what)
    if not ok:
        FAILS.append(what)


class Dev:
    def __init__(self, port: str) -> None:
        self.s = serial.Serial(port, 115200, timeout=1.0)
        time.sleep(0.2)
        self.s.reset_input_buffer()

    def cmd(self, line: str, timeout: float = 2.0) -> str:
        self.s.reset_input_buffer()
        self.s.write((line + "\n").encode())
        end = time.time() + timeout
        while time.time() < end:
            r = self.s.readline().decode(errors="replace").strip()
            if r and not r.startswith("."):
                return r
        raise TimeoutError(f"no reply to {line!r}")

    def status(self) -> dict:
        return json.loads(self.cmd("status"))


def idle_checks(st: dict) -> None:
    check(st["mode"] == "idle", f"mode idle ({st['mode']})")
    check(st["cmd_ma"] == 0, f"commanded 0 mA ({st['cmd_ma']})")
    check(st["relay"] == -1, f"relays released, electrodes on one node ({st['relay']})")
    check(st["meas_ma"] < 0.1, f"readback under 0.1 mA ({st['meas_ma']})")
    check(not st["fault"], f"no fault ({st['msg']!r})")


def watch(d: Dev, reply: str, max_s: float = 6.0) -> list[dict]:
    print(reply)
    trace, t0 = [], time.time()
    while time.time() - t0 < max_s:
        st = d.status()
        st["t"] = round(time.time() - t0, 3)
        trace.append(st)
        if st["mode"] == "idle" and time.time() - t0 > 0.2:
            break
        time.sleep(0.05)
    return trace


def summarize(trace: list[dict], ma: float) -> None:
    active = [s for s in trace if s["mode"] != "idle"]
    relays = [s["relay"] for s in trace]
    seq = [r for i, r in enumerate(relays) if i == 0 or r != relays[i - 1]]
    peak = max((s["meas_ma"] for s in active), default=0.0)
    hv = [s["hv"] for s in active]
    print(f"samples {len(trace)}, active {len(active)}, relay sequence {seq}, peak readback {peak:.3f} mA, "
          f"HV {min(hv, default=0):.1f}-{max(hv, default=0):.1f} V, last msg {trace[-1]['msg']!r}")
    for s in trace:
        print(f"  t={s['t']:5.2f} {s['mode']:4s} relay={s['relay']:2d} cmd={s['cmd_ma']:.3f} meas={s['meas_ma']:.3f} hv={s['hv']:.1f}")
    check(any(s["mode"] != "idle" and s["cmd_ma"] > 0 for s in trace), "pulse delivered (HV reached ready)")
    check(peak <= ma * 1.1 + 0.05, f"peak readback {peak:.3f} <= commanded {ma} +10%")
    check(peak >= ma * 0.8 - 0.05, f"peak readback {peak:.3f} >= 80% of commanded {ma} (dummy load connected?)")
    idle_checks(trace[-1])


# (offset s from T0, name, serial command, meter expectation, action for the person at the bench)
SUITE = [
    (0, "T1 polarity reversed", "pulse 1.0 3000 1 1 dc", "-2.2 V for 3 s", ""),
    (12, "T2 over-limit 5 mA x 10 s", "pulse 5 10000 1 0 dc", "+4.4 V, back to 0 after 3 s", ""),
    (16.5, "T3 inside cooldown", "pulse 0.5 3000 1 0 dc", "stays 0 V (refused)", ""),
    (28, "T4 sine 1 mA 1 Hz", "pulse 1.0 3000 1 0 sine", "swings + and -, ends 0 V", ""),
    (40, "T5 stop command at 1 s", "pulse 1.0 3000 1 0 dc", "+2.2 V, drops to 0 at ~1 s", "stop@1.0"),
    (52, "T6 kill switch", "pulse 1.0 3000 1 0 dc", "+2.2 V, 0 V when you flip it", "PERSON: flip kill switch OFF ~1 s in, ON again after"),
    (64, "T7 reset button", "pulse 1.0 3000 1 0 dc", "+2.2 V, 0 V when you press it", "PERSON: press XIAO RESET ~1 s in"),
]


def _reconnect(port: str, wait_s: float = 25.0) -> "Dev | None":
    end = time.time() + wait_s
    while time.time() < end:
        try:
            d = Dev(port)
            d.status()
            return d
        except Exception:
            time.sleep(1.0)
    return None


def suite(port: str, lead: float) -> int:
    d = Dev(port)
    idle_checks(d.status())
    t0 = time.time() + lead
    print(f"T0 = {time.strftime('%H:%M:%S', time.localtime(t0))}")
    for off, name, cmd, expect, action in SUITE:
        start = t0 + off
        print(f"{time.strftime('%H:%M:%S', time.localtime(start))}  {name}: expect {expect}" + (f"  [{action}]" if action else ""))
    for off, name, cmd, expect, action in SUITE:
        while time.time() < t0 + off:
            time.sleep(0.02)
        print(f"\n== {name}  {time.strftime('%H:%M:%S')}")
        try:
            r = d.cmd(cmd)
        except Exception as e:
            check(False, f"{name}: command failed ({e})")
            continue
        print(f"   reply: {r}")
        if name.startswith("T3"):
            check(r.startswith("429") and "cooldown" in r, f"{name}: refused with cooldown")
            continue
        if not r.startswith("200"):
            check(False, f"{name}: accepted")
            continue
        if name.startswith("T2"):
            check("2.00 mA" in r and "3000 ms" in r, f"{name}: clamped to 2.00 mA / 3000 ms")
        trace, ts, stopped_at, rebooted = [], time.time(), None, False
        while time.time() - ts < 5.5:
            if action.startswith("stop@") and stopped_at is None and time.time() - ts >= float(action[5:]):
                print("   " + d.cmd("stop"))
                stopped_at = round(time.time() - ts, 2)
            try:
                st = d.status()
            except Exception:
                rebooted = True
                break
            st["t"] = round(time.time() - ts, 2)
            trace.append(st)
            if st["mode"] == "idle" and st["t"] > 0.3:
                break
            time.sleep(0.05)
        active = [s for s in trace if s["mode"] != "idle"]
        end_t = trace[-1]["t"] if trace else None
        relays = [s["relay"] for s in trace]
        seq = [r_ for i, r_ in enumerate(relays) if i == 0 or r_ != relays[i - 1]]
        peak = max((s["meas_ma"] for s in active), default=0.0)
        print(f"   board: idle at t={end_t}s, relays {seq}, peak meas {peak:.3f} mA, "
              f"cmd max {max((s['cmd_ma'] for s in active), default=0):.2f}, fault {trace[-1]['fault'] if trace else '?'}")
        if name.startswith("T1"):
            check(1 in relays and 0 not in relays, f"{name}: relay 2 drove, relay 1 did not")
        if name.startswith("T2"):
            check(end_t is not None and end_t <= 4.0, f"{name}: ended by 4 s ({end_t})")
            check(peak <= 2.3, f"{name}: peak readback {peak:.2f} <= 2.3 mA")
        if name.startswith("T4"):
            check(0 in relays and 1 in relays, f"{name}: both relays drove (bipolar)")
        if name.startswith("T5"):
            check(end_t is not None and stopped_at is not None and end_t - stopped_at <= 0.3,
                  f"{name}: idle within 0.3 s of stop (stop {stopped_at}, idle {end_t})")
        if name.startswith("T7"):
            if rebooted:
                print("   board went away (reset). Reconnecting...")
                d = _reconnect(port)
                if d is None:
                    check(False, f"{name}: board back after reset")
                    break
                st = d.status()
                check(st["pulses_logged"] == 0, f"{name}: board rebooted (pulse log cleared)")
                idle_checks(st)
            else:
                check(False, f"{name}: board did not reset during the pulse (button not pressed in time?)")
        elif trace:
            idle_checks(trace[-1])
    print(f"\n{len(FAILS)} FAIL" if FAILS else "\nall PASS (board side). Meter readings are the other half.")
    return 1 if FAILS else 0


def hourcap(port: str) -> int:
    """31 back-to-back tiny pulses: 30 accepted, the 31st refused with hourly_limit. Resets the board after."""
    d = Dev(port)
    idle_checks(d.status())
    n0 = d.status()["pulses_logged"]
    accepted = n0
    while accepted < 30:
        while d.status()["cooldown_ms"] > 0 or d.status()["mode"] != "idle":
            time.sleep(0.2)
        r = d.cmd("pulse 0.1 600 1 0 dc")
        if r.startswith("200"):
            accepted += 1
            print(f"   {accepted:2d} {r}")
        else:
            print(f"   refused early: {r}")
            break
    while d.status()["cooldown_ms"] > 0 or d.status()["mode"] != "idle":
        time.sleep(0.2)
    r = d.cmd("pulse 0.1 600 1 0 dc")
    check(accepted == 30 and r.startswith("429") and "hourly_limit" in r, f"pulse 31 refused with hourly_limit ({r})")
    st = d.status()
    check(st["hour_full"], "status says hour_full")
    print("resetting the board to clear the hour log")
    d.s.dtr = False
    d.s.rts = True
    time.sleep(0.1)
    d.s.rts = False
    d.s.close()
    time.sleep(2)
    d = _reconnect(port)
    check(d is not None and d.status()["pulses_logged"] == 0, "board back with log cleared")
    print(f"\n{len(FAILS)} FAIL" if FAILS else "\nall PASS")
    return 1 if FAILS else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=PORT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("idle")
    sub.add_parser("power")
    b = sub.add_parser("boost-sweep")
    b.add_argument("--target", type=float, default=22.0)
    b.add_argument("--ceiling", type=float, default=25.0)
    b.add_argument("--step", type=float, default=5.0)
    bp = sub.add_parser("boostpct")
    bp.add_argument("pct", type=float)
    p = sub.add_parser("pulse")
    p.add_argument("ma", type=float)
    p.add_argument("ms", type=int)
    p.add_argument("--hz", type=float, default=1.0)
    p.add_argument("--pol", type=int, default=0)
    p.add_argument("--mode", choices=["sine", "dc"], default="sine")
    sub.add_parser("limits")
    su = sub.add_parser("suite")
    su.add_argument("--lead", type=float, default=20.0, help="seconds before test 1 starts")
    sub.add_parser("hourcap")
    a = ap.parse_args()
    if a.cmd == "suite":
        return suite(a.port, a.lead)
    if a.cmd == "hourcap":
        return hourcap(a.port)
    d = Dev(a.port)

    if a.cmd == "status":
        print(json.dumps(d.status()))
    elif a.cmd == "idle":
        idle_checks(d.status())
    elif a.cmd == "power":
        st = d.status()
        idle_checks(st)
        check(3.3 <= st["hv"] <= 4.3, f"HV rail at battery minus diode, 3.3-4.3 V ({st['hv']})")
    elif a.cmd == "boost-sweep":
        idle_checks(d.status())
        pct, rows = 0.0, []
        try:
            while pct < 45:
                pct = min(pct + a.step, 45)
                r = d.cmd(f"boost {pct}")
                hv = d.status()["hv"]
                rows.append((pct, hv))
                print(f"  {r}   status hv {hv:.2f}")
                if hv >= a.ceiling or hv >= a.target:
                    break
        finally:
            print(d.cmd("boost 0"))
        time.sleep(1.0)
        st = d.status()
        hit = [p for p, hv in rows if hv >= a.target]
        check(bool(hit), f"reached {a.target} V (first at {hit[0] if hit else None}%)")
        check(max(hv for _, hv in rows) < 28, f"never reached the 28 V cutoff (max {max(hv for _, hv in rows):.2f})")
        check(not st["fault"], f"no fault after sweep ({st['msg']!r})")
        print("Now: meter on the HV bus at that duty, and touch-test Q1, the inductor and the 1N5819 for heat.")
    elif a.cmd == "boostpct":
        print(d.cmd(f"boostpct {a.pct}"))
    elif a.cmd == "pulse":
        idle_checks(d.status())
        r = d.cmd(f"pulse {a.ma} {a.ms} {a.hz} {a.pol} {a.mode}")
        if not r.startswith("200"):
            check(False, f"pulse accepted ({r})")
        else:
            summarize(watch(d, r, max_s=a.ms / 1000 + 3), min(a.ma, 2.0))
    elif a.cmd == "limits":
        r = d.cmd("pulse 5 10000 1 0 dc")
        check(r.startswith("200") and "2.00 mA" in r and "3000 ms" in r, f"5 mA / 10 s clamped to 2 mA / 3 s ({r})")
        time.sleep(0.8)
        print(d.cmd("stop"))
        st = d.status()
        idle_checks(st)
        r = d.cmd("pulse 0.5 1000 1 0 sine")
        check(r.startswith("429") and "cooldown" in r, f"second pulse inside cooldown refused ({r})")
    print(f"\n{len(FAILS)} FAIL" if FAILS else "\nall PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
