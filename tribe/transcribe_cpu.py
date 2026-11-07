"""CPU stand-in for tribev2.eventstransforms.ExtractWordsFromAudio._get_transcript_from_audio.

Same uvx whisperx call and the same JSON->TSV conversion (eventstransforms.py:111-158),
but --compute_type int8, because faster-whisper has no float16 on CPU.
Writes <wav>.tsv, which ExtractWordsFromAudio picks up instead of re-running whisperx.
"""
import json, subprocess, sys, tempfile, time
from pathlib import Path
import pandas as pd

COLUMNS = ["text", "start", "duration", "sequence_id", "sentence"]


def transcribe(wav: Path) -> Path:
    t0 = time.time()
    with tempfile.TemporaryDirectory() as out:
        cmd = ["uvx", "whisperx", str(wav), "--model", "large-v3", "--language", "en",
               "--device", "cpu", "--compute_type", "int8", "--batch_size", "16",
               "--align_model", "WAV2VEC2_ASR_LARGE_LV60K_960H", "--output_dir", out, "--output_format", "json"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("whisperx failed:\n" + r.stderr[-3000:])
        tr = json.loads((Path(out) / f"{wav.stem}.json").read_text())
    words = []
    for i, seg in enumerate(tr["segments"]):
        sentence = seg["text"].replace('"', "")
        for w in seg["words"]:
            if "start" not in w:
                continue
            words.append({"text": w["word"].replace('"', ""), "start": w["start"],
                          "duration": w["end"] - w["start"], "sequence_id": i, "sentence": sentence})
    df = pd.DataFrame(words, columns=COLUMNS)  # silent clips: header only, zero words
    df.to_csv(wav.with_suffix(".tsv"), sep="\t", index=False)
    print(f"{len(df)} words in {time.time()-t0:.1f}s ->", wav.with_suffix(".tsv"))
    return wav.with_suffix(".tsv")


if __name__ == "__main__":
    transcribe(Path(sys.argv[1]))
