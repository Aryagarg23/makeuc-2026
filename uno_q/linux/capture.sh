#!/bin/sh
# Packet metadata capture on the Tailscale interface (exit-node traffic).
# One tab-separated line per packet, no header, empty field = not present.
# Column order is the contract with pipeline/gvs_pipeline/packets.py:COLUMNS
# (pipeline/tests/test_capture_contract.py checks they match).
# Multi-value fields are joined with ','.
# Usage: capture.sh [interface]   (default tailscale0). Run as a user in the
# 'wireshark' group, or as root. Output goes to stdout.
IFACE="${1:-tailscale0}"
exec tshark -i "$IFACE" -l -n -T fields -E separator='	' -E aggregator=, \
  -e frame.time_epoch \
  -e ip.src \
  -e ip.dst \
  -e ipv6.src \
  -e ipv6.dst \
  -e tcp.srcport \
  -e tcp.dstport \
  -e udp.srcport \
  -e udp.dstport \
  -e frame.len \
  -e dns.qry.name \
  -e dns.a \
  -e dns.aaaa \
  -e tls.handshake.extensions_server_name \
  -e http.host
