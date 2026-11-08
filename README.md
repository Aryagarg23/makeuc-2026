# makeuc-2026

Packet capture over the tailnet, bucketed by content type, driving a GVS aversive-conditioning rig.

- `gvs/` the GVS device as built: XIAO ESP32-C3 firmware (HTTP), perfboard layout, net check, SPICE sim, build guide (`gvs/README.md`)
- `uno_q/` Arduino Uno Q (MCU sketch + Linux side)
- `pipeline/` capture, classify, intensity, HTTP link to the device
- `tribe/` TRIBE v2 scoring of enrollment screen recordings on the GPU box (caps bucket weights)
- `research/` sourced write-ups: GVS, conditioning, traffic fingerprinting, UNO Q exit node, TRIBE v2 (`research/README.md` is the index)

Before the GVS touches a head: `gvs/README.md` bench steps, then `research/gvs.md` (on-head procedure).
- `legacy/` the first ESP32 serial controller and its SD card, superseded by `gvs/`
