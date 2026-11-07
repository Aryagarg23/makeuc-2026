"""Attribute packets to services and summarise each service per time window."""
from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Iterator

from .packets import Packet

# Multi-label public suffixes we expect on a personal tailnet. Not the full PSL:
# hosts under an unlisted multi-label suffix collapse one label too far.
_MULTI_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "com.au", "net.au", "co.jp", "co.in", "com.br",
    "co.nz", "com.cn", "com.mx", "co.kr",
}

UNKNOWN = "?"
N_FEATURES = 6


def service_of(host: str) -> str:
    """Registrable domain: last two labels, or three under a known multi-label suffix."""
    labels = [l for l in host.lower().rstrip(".").split(".") if l]
    if len(labels) <= 2:
        return ".".join(labels)
    if ".".join(labels[-2:]) in _MULTI_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


class HostMap:
    """IP -> hostname, learned from DNS answers, TLS SNI and HTTP Host."""

    def __init__(self) -> None:
        self._ip_host: dict[str, str] = {}

    def learn(self, p: Packet) -> None:
        if p.dns_name and p.dns_answers:
            for ip in p.dns_answers:
                self._ip_host[ip] = p.dns_name
        name = p.sni or p.http_host
        if name:
            self._ip_host[p.dst] = name

    def server_and_host(self, p: Packet) -> tuple[str, str | None]:
        """Return (server_ip, host). Server is whichever end we have a name for, else dst."""
        if p.dst in self._ip_host:
            return p.dst, self._ip_host[p.dst]
        if p.src in self._ip_host:
            return p.src, self._ip_host[p.src]
        return unnamed_server(p), None


def _is_tailnet(ip: str) -> bool:
    """Tailscale client addresses: 100.64.0.0/10 and fd7a:115c:a1e0::/48."""
    if ip.lower().startswith("fd7a:115c:a1e0:"):
        return True
    parts = ip.split(".")
    return len(parts) == 4 and parts[0] == "100" and 64 <= int(parts[1]) <= 127


def unnamed_server(p: Packet) -> str:
    """Server end of a packet with no known name: well-known port side, else the non-tailnet side, else dst."""
    if p.sport is not None and p.sport < 1024 and not (p.dport is not None and p.dport < 1024):
        return p.src
    if p.dport is not None and p.dport < 1024:
        return p.dst
    if _is_tailnet(p.dst) and not _is_tailnet(p.src):
        return p.src
    return p.dst


@dataclass(frozen=True)
class Observation:
    window_start: float
    service: str  # registrable domain, or UNKNOWN when no name was ever seen
    server: str  # server IP; distinguishes unnamed flows from each other
    bytes: int
    packets: int
    features: tuple[float, ...]
    window_s: float = 10.0  # features 0, 1 and 5 depend on window length; prototypes only compare at equal length


def features(pkts: list[Packet], servers: set[str], window_s: float) -> tuple[float, ...]:
    """Six flow-shape features, each roughly in [0, 1].

    0 log-bytes, 1 log-packets, 2 mean size / 1500, 3 fraction of packets > 1200 B,
    4 fraction of bytes flowing server->client, 5 burstiness (CV of per-second bytes, capped at 3, /3).
    """
    total = sum(p.length for p in pkts)
    n = len(pkts)
    down = sum(p.length for p in pkts if p.src in servers)
    per_sec: dict[int, int] = defaultdict(int)
    t0 = min(p.ts for p in pkts)
    for p in pkts:
        per_sec[int(p.ts - t0)] += p.length
    slots = max(1, int(math.ceil(window_s)))
    series = [per_sec.get(i, 0) for i in range(slots)]
    mean = sum(series) / slots
    var = sum((x - mean) ** 2 for x in series) / slots
    cv = math.sqrt(var) / mean if mean > 0 else 0.0
    return (
        math.log1p(total) / math.log1p(1e8),
        math.log1p(n) / math.log1p(1e5),
        min(total / n / 1500.0, 1.0),
        sum(1 for p in pkts if p.length > 1200) / n,
        down / total if total else 0.0,
        min(cv, 3.0) / 3.0,
    )


def windows(
    packets: Iterable[Packet], window_s: float = 10.0, step_s: float | None = None
) -> Iterator[list[Observation]]:
    """Windows [k*step_s, k*step_s + window_s). step_s=None means tumbling (step = window).

    Yields the observations of each non-empty window once a later packet closes it, then the
    windows still open at end of input. Packets must arrive in non-decreasing ts order (tshark
    live output does). A packet is attributed to a service when it arrives, using names learned
    up to then.
    """
    step = window_s if step_s is None else step_s
    if not 0 < step <= window_s:
        raise ValueError("need 0 < step_s <= window_s")
    hosts = HostMap()
    buf: deque[tuple[Packet, tuple[str, str], str]] = deque()
    k: int | None = None  # earliest window not yet emitted

    def first_window(ts: float) -> int:
        return math.floor((ts - window_s) / step) + 1

    def emit(idx: int) -> list[Observation]:
        lo, hi = idx * step, idx * step + window_s
        groups: dict[tuple[str, str], list[Packet]] = defaultdict(list)
        servers: dict[tuple[str, str], set[str]] = defaultdict(set)
        for p, key, server in buf:
            if lo <= p.ts < hi:
                groups[key].append(p)
                servers[key].add(server)
        return [
            Observation(
                window_start=lo,
                service=service,
                server=server,
                bytes=sum(p.length for p in pkts),
                packets=len(pkts),
                features=features(pkts, servers[(service, server)], window_s),
                window_s=window_s,
            )
            for (service, server), pkts in sorted(groups.items())
        ]

    def advance() -> None:
        nonlocal k
        k += 1
        while buf and buf[0][0].ts < k * step:
            buf.popleft()
        if buf:
            k = max(k, first_window(buf[0][0].ts))

    for p in packets:
        hosts.learn(p)
        if k is None:
            k = first_window(p.ts)
        while k * step + window_s <= p.ts:
            out = emit(k)
            if out:
                yield out
            advance()
            if not buf:
                k = first_window(p.ts)
        server, host = hosts.server_and_host(p)
        service = service_of(host) if host else UNKNOWN
        key = (service, server if service == UNKNOWN else "")
        buf.append((p, key, server))
    while buf:
        out = emit(k)
        if out:
            yield out
        advance()
