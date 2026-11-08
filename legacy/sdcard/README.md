# sdcard

microSD preparation for the ESP32 data logger.

## Format

MBR partition map, one FAT32 volume named `GVSLOG`. Built with `diskutil eraseDisk FAT32 GVSLOG MBRFormat`.

## Layout

    /config.json        device configuration (below)
    /README.txt         what the card is for, config keys
    /log/trials.csv     header: uptime_ms,bucket,intensity,duty,ms,result,reason
    /.metadata_never_index   keeps Spotlight off

`layout/` in this directory is the reproducible copy of these files.

## Config contract

`config.json`, default `{"device_name":"gvs-01","max_duty":0.4,"wifi_ssid":"","wifi_password":""}`

- `device_name`: string
- `max_duty`: number in (0, 0.6]. The firmware ceiling is 0.6; config may only lower it.
- `wifi_ssid`: string. Empty means serial-only mode (the default).
- `wifi_password`: string

## Scripts

- `prepare_sd.sh diskN`: refuses unless the disk is external, removable and under 64 GB, and you type the identifier back. Then erases it and writes `layout/`.
- `verify_sd.py /Volumes/GVSLOG`: stdlib Python 3. Checks config.json parses, key types, `0 < max_duty <= 0.6`, and trials.csv's first line equals the header. Exit code 1 on failure.

## Status

Verified on the Mac only (verify_sd.py passes on the mounted card). Not yet tested on the ESP32; the SD module isn't wired.

## Known leftovers

macOS recreated `.Spotlight-V100` on first mount, before `.metadata_never_index` could exist, and it can't be removed from a mounted FAT volume here (Operation not permitted). It is harmless: indexing is turned off for the volume and the marker file is present. The script tries to remove it and only warns on failure.
