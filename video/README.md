# Pitch video tools

These cut **real clips** together. Nothing is generated except the cards and the robot voice. The scene-by-scene plan, fact notes and shot list are in `script.md`.

**Setup:**
```bash
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/pip install pillow numpy "opencv-python-headless<5"
```
OpenCV 5 dropped the bundled face cascades that `--eyes` uses, hence `<5`.

## Building the video

1. Put your footage in `clips/` and any recorded voiceover in `vo/`. Both are git-ignored, along with `work/` and `out/`.
2. Copy `edl.example.json` to `edl.json`, then list your segments in order: clips with in/out points, a look, an audio treatment, and an optional voiceover, plus cards. The format is documented at the top of `build.py`.
3. Run `.venv/bin/python build.py edl.json out/pitch.mp4`. Every segment is rendered to 1920×1080 at 30 fps with 48 kHz audio, then joined without re-encoding.

## Single pieces, for previewing

```bash
.venv/bin/python fx.py look clips/x.mp4 work/x_kids.mp4 --look kids --in 3 --out 9
.venv/bin/python fx.py look clips/news.mp4 work/news_ds.mp4 --look dedsec --eyes
.venv/bin/python fx.py voice work/x_kids.mp4 work/x_meme.mp4 --voice meme+echo
.venv/bin/python fx.py tts "Edit your reflexes." work/sting.wav --speaker Trinoids
.venv/bin/python cards.py demo work/cards
```

## Looks and voices

| Name | What it does |
|---|---|
| `kids` | Bloom, saturation 1.75, VHS grain, slight RGB fringe, 4:3 picture in a round vignette |
| `dedsec` | Teal/magenta grade, RGB split, scanlines, glitch tears every ~2.5 s. `--eyes` pixelates a band over each detected face's eyes. |
| `clean` | Scale and pad only |
| `meme` | Pitch ×1.6, same speed |
| `echo` | Three fading repeats |
| `tts` | macOS `say` (Zarvox / Trinoids / …), bit-crushed |

## Verified

- `edl.example.json` builds into a 35.9 s, 1920×1080/30 H.264 + AAC 48 kHz file in about 19 s on this Mac.
- Frames checked: the dedsec title, the software map and the results card.

## Not verified

- `--eyes` on real faces. The test footage had none.
- `geq` glitch speed on long 4K clips. It runs at a few frames per second, so cut clips to length first.
