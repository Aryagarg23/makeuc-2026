#!/bin/sh
# Upload the HVAC videos and poster frames to Supabase Storage, where Supabase's CDN serves them.
#
#   SUPABASE_SERVICE_KEY=<service_role key> sh video/upload_hvac_media.sh
#
# The bucket "hvac" already exists (public read, 50 MB per file, video/mp4 and image types only).
# Nobody but the service_role key can write to it, so the key goes in your shell and nowhere else: don't
# commit it and don't paste it into a chat. Dashboard -> Project Settings -> API Keys -> service_role.
# Files come from video/out/hvac-upload/. The site reads them from
#   https://vircgxpcwyvniemqmdyi.supabase.co/storage/v1/object/public/hvac/<name>
#
# Or with the Supabase CLI after `npx supabase login` (what was actually used on 2026-11-08):
#   for f in pitch.mp4 pitch.jpg friend.mp4 friend.jpg; do
#     npx supabase storage cp --experimental --yes --remote=vircgxpcwyvniemqmdyi \
#       --content-type <video/mp4|image/jpeg> --cache-control max-age=31536000 video/out/hvac-upload/$f ss:///hvac/$f
#   done
# Served by Supabase's CDN with range requests and `cache-control: public, max-age=31536000`.
set -eu
: "${SUPABASE_SERVICE_KEY:?set SUPABASE_SERVICE_KEY (the service_role key)}"
REF=vircgxpcwyvniemqmdyi
DIR="$(cd "$(dirname "$0")" && pwd)/out/hvac-upload"
for f in pitch.mp4 pitch.jpg friend.mp4 friend.jpg; do
  case "$f" in *.mp4) ct=video/mp4 ;; *) ct=image/jpeg ;; esac
  [ -f "$DIR/$f" ] || { echo "missing $DIR/$f"; exit 1; }
  curl -sS -f -X POST "https://$REF.supabase.co/storage/v1/object/hvac/$f" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" -H "apikey: $SUPABASE_SERVICE_KEY" \
    -H "Content-Type: $ct" -H "x-upsert: true" --data-binary @"$DIR/$f" >/dev/null && echo "uploaded $f"
done
for f in pitch.mp4 pitch.jpg friend.mp4 friend.jpg; do
  printf "%-12s " "$f"; curl -s -o /dev/null -w "%{http_code} %{content_type}\n" "https://$REF.supabase.co/storage/v1/object/public/hvac/$f"
done
