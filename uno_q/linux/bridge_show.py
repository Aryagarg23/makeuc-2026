#!/usr/bin/env python3
"""Call the MCU sketch (matrix_status.ino) from Linux over the Arduino Router.

Usage:
  bridge_show.py show <bucket 0-9> <intensity 0..1>
  bridge_show.py clear

Speaks msgpack-rpc on /var/run/arduino-router.sock, the interface documented in
the UNO Q user manual ("Interacting via Unix Socket"). Needs python3-msgpack
(apt install python3-msgpack). Exit 0 only if the router returned error=None.
"""
import socket
import sys

import msgpack

SOCKET_PATH = "/var/run/arduino-router.sock"


def call(method, params, msgid=1, timeout=5.0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(SOCKET_PATH)
        s.sendall(msgpack.packb([0, msgid, method, params]))
        unpacker = msgpack.Unpacker(raw=False)
        while True:
            chunk = s.recv(4096)
            if not chunk:
                raise RuntimeError("router closed the socket without a response")
            unpacker.feed(chunk)
            for msg in unpacker:
                if msg[0] == 1 and msg[1] == msgid:
                    return msg[2], msg[3]


def main(argv):
    if len(argv) == 4 and argv[1] == "show":
        bucket = int(argv[2])
        intensity = float(argv[3])  # always float: the sketch's show() takes a float
        if not 0 <= bucket <= 9 or not 0.0 <= intensity <= 1.0:
            print("bucket must be 0-9, intensity 0..1", file=sys.stderr)
            return 2
        err, result = call("show", [bucket, intensity])
    elif len(argv) == 2 and argv[1] == "clear":
        err, result = call("clear", [])
    else:
        print(__doc__, file=sys.stderr)
        return 2
    print(f"error={err!r} result={result!r}")
    return 0 if err is None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
