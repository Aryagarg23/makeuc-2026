#!/bin/sh
# Double-click (or `open` this file): starts the Bluetooth relay in Terminal.app, which can hold Bluetooth permission.
cd "$(dirname "$0")/../.." && exec pipeline/.venv/bin/python gvs/tools/ble_bridge.py
