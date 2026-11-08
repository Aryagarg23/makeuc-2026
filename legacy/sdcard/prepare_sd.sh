#!/bin/bash
# Usage: prepare_sd.sh diskN   -- ERASES the disk, writes the GVSLOG layout.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
id="${1:-}"; id="${id#/dev/}"
[[ "$id" =~ ^disk[0-9]+$ ]] || { echo "usage: $0 diskN" >&2; exit 2; }
info="$(diskutil info "/dev/$id")"
field() { echo "$info" | awk -F': *' -v k="$1" '$1 ~ "^ *"k"$" {print $2; exit}'; }
[[ "$(field 'Device Location')" == "External" ]] || { echo "refusing: not external" >&2; exit 1; }
[[ "$(field 'Removable Media')" == "Removable" ]] || { echo "refusing: not removable" >&2; exit 1; }
bytes="$(echo "$info" | sed -n 's/.*Disk Size:.*(\([0-9]*\) Bytes).*/\1/p' | head -1)"
(( bytes > 0 && bytes < 64000000000 )) || { echo "refusing: size '$bytes' not under 64 GB" >&2; exit 1; }
diskutil list "/dev/$id"
read -r -p "Type '$id' to ERASE it: " typed
[[ "$typed" == "$id" ]] || { echo "aborted" >&2; exit 1; }
diskutil eraseDisk FAT32 GVSLOG MBRFormat "/dev/$id"
vol=/Volumes/GVSLOG
mdutil -i off "$vol" >/dev/null 2>&1 || true
touch "$vol/.metadata_never_index"
cp "$here/layout/config.json" "$here/layout/README.txt" "$vol/"
mkdir -p "$vol/log"; cp "$here/layout/log/trials.csv" "$vol/log/"
dot_clean -m "$vol" || true
for j in .fseventsd .Spotlight-V100 .Trashes; do
  rm -rf "$vol/$j" 2>/dev/null || echo "note: could not remove $j (harmless; .metadata_never_index is set)"
done
find "$vol" -maxdepth 2 -name '._*' -not -path "$vol/.Spotlight-V100/*" -delete 2>/dev/null || true
sync
echo "done; verify with: python3 $here/verify_sd.py $vol"
