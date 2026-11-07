"""Parse tshark `-T fields -E separator=/t` lines into Packet records.

The column order is the contract with uno_q/linux/capture.sh. Change both together.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COLUMNS: tuple[str, ...] = (
    "frame.time_epoch",
    "ip.src",
    "ip.dst",
    "ipv6.src",
    "ipv6.dst",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "frame.len",
    "dns.qry.name",
    "dns.a",
    "dns.aaaa",
    "tls.handshake.extensions_server_name",
    "http.host",
)


@dataclass(frozen=True)
class Packet:
    ts: float
    src: str
    dst: str
    length: int
    sport: int | None = None
    dport: int | None = None
    dns_name: str | None = None
    dns_answers: tuple[str, ...] = field(default_factory=tuple)
    sni: str | None = None
    http_host: str | None = None


def _first(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    return value.split(",")[0].strip() or None


def _port(tcp: str, udp: str) -> int | None:
    v = _first(tcp) or _first(udp)
    return int(v) if v is not None else None


def parse_line(line: str, columns: tuple[str, ...] = COLUMNS) -> Packet | None:
    """Return a Packet, or None for lines with no timestamp, address or length."""
    parts = line.rstrip("\n").split("\t")
    if len(parts) < len(columns):
        parts += [""] * (len(columns) - len(parts))
    f = dict(zip(columns, parts))
    ts, length = _first(f["frame.time_epoch"]), _first(f["frame.len"])
    src = _first(f["ip.src"]) or _first(f["ipv6.src"])
    dst = _first(f["ip.dst"]) or _first(f["ipv6.dst"])
    if ts is None or length is None or src is None or dst is None:
        return None
    try:
        ts_f, len_i = float(ts), int(length)
    except ValueError:
        return None
    answers = tuple(
        a.strip()
        for col in ("dns.a", "dns.aaaa")
        for a in f[col].split(",")
        if a.strip()
    )
    return Packet(
        ts=ts_f,
        src=src,
        dst=dst,
        length=len_i,
        sport=_port(f["tcp.srcport"], f["udp.srcport"]),
        dport=_port(f["tcp.dstport"], f["udp.dstport"]),
        dns_name=_first(f["dns.qry.name"]),
        dns_answers=answers,
        sni=_first(f["tls.handshake.extensions_server_name"]),
        http_host=_first(f["http.host"]),
    )


def to_line(p: Packet, columns: tuple[str, ...] = COLUMNS) -> str:
    """Inverse of parse_line for IPv4/IPv6 packets; used by tests and fixtures."""
    v6 = ":" in p.src
    sport = "" if p.sport is None else str(p.sport)
    dport = "" if p.dport is None else str(p.dport)
    v4a = ",".join(a for a in p.dns_answers if ":" not in a)
    v6a = ",".join(a for a in p.dns_answers if ":" in a)
    f = {
        "frame.time_epoch": repr(p.ts),
        "ip.src": "" if v6 else p.src,
        "ip.dst": "" if v6 else p.dst,
        "ipv6.src": p.src if v6 else "",
        "ipv6.dst": p.dst if v6 else "",
        "tcp.srcport": sport,
        "tcp.dstport": dport,
        "udp.srcport": "",
        "udp.dstport": "",
        "frame.len": str(p.length),
        "dns.qry.name": p.dns_name or "",
        "dns.a": v4a,
        "dns.aaaa": v6a,
        "tls.handshake.extensions_server_name": p.sni or "",
        "http.host": p.http_host or "",
    }
    return "\t".join(f[c] for c in columns)
