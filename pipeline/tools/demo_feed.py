"""Synthetic, real-time packet lines for trying the dashboard without a capture (dry run only).

  python3 tools/demo_feed.py | python3 -m gvs_pipeline --store /tmp/demo/p.json --window 3 live --dashboard 8090

Every 20 s it rotates between a short-video download (tiktokv.com), a chat (whatsapp.net) and a video
stream (googlevideo.com), with a small background flow (icloud.com) throughout. Lines are in
packets.COLUMNS order, stamped with wall-clock time. Nothing here is real traffic.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gvs_pipeline.packets import Packet, to_line  # noqa: E402

CLIENT = "100.64.0.2"
PHASES = [("9.9.9.9", "v16.tiktokv.com", 1400, 60), ("4.4.4.4", "web.whatsapp.net", 160, 4),
          ("8.8.4.4", "rr3.googlevideo.com", 1400, 45)]


def main() -> int:
    named: set[str] = set()
    t_end = time.time() + 3600
    while time.time() < t_end:
        now = time.time()
        server, host, size, pps = PHASES[int(now // 20) % len(PHASES)]
        out = []
        for srv, h in ((server, host), ("17.1.1.1", "gateway.icloud.com")):
            if h not in named:  # one SNI packet names the flow, as on a real TLS start
                out.append(Packet(now, CLIENT, srv, 300, dport=443, sni=h))
                named.add(h)
        for i in range(pps // 10):
            out.append(Packet(now + i / pps, server, CLIENT, size, sport=443))
        out.append(Packet(now, "17.1.1.1", CLIENT, 200, sport=443))
        sys.stdout.write("".join(to_line(p) + "\n" for p in out))
        sys.stdout.flush()
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
