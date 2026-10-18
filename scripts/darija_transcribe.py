#!/usr/bin/env -S uv run --python 3.12 --with "faster-whisper" --with "av<14" python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "faster-whisper",
#     "av<14",
# ]
# ///
"""
darija_transcribe.py

Word-level timestamped transcription using faster-whisper.
Configured for Moroccan Darija (Arabic dialect code: ar) and code-switching speech.
Outputs structured JSON with tick-accurate word onsets and offsets.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_audio(media_path: Path, output_wav: Path) -> None:
    """Extract audio from video file to 16kHz mono 16-bit WAV."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(media_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_wav),
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {res.stderr}")


def transcribe_file(
    media_path: str,
    output_path: str,
    model_size: str = "small",
    language: str = "ar",
    device: str = "auto",
) -> None:
    media_file = Path(media_path).resolve()
    if not media_file.exists():
        sys.exit(f"Error: media file not found: {media_file}")

    from faster_whisper import WhisperModel

    compute_type = "int8" if device == "cpu" else "default"
    print(f"Loading Whisper model '{model_size}' (device={device}, compute_type={compute_type})...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "audio.wav"
        print("Extracting 16kHz mono audio with ffmpeg...")
        extract_audio(media_file, wav_path)

        print(f"Transcribing {media_file.name} (language={language}, word_timestamps=True)...")
        segments_gen, info = model.transcribe(
            str(wav_path),
            word_timestamps=True,
            language=language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        segments_data = []
        total_words = 0
        for seg in segments_gen:
            words_data = []
            if seg.words:
                for w in seg.words:
                    words_data.append(
                        {
                            "word": w.word,
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                            "probability": round(w.probability, 3),
                        }
                    )
                    total_words += 1
            segments_data.append(
                {
                    "id": seg.id,
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                    "words": words_data,
                }
            )

        result = {
            "source_media": str(media_file),
            "duration": round(info.duration, 3),
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "total_words": total_words,
            "segments": segments_data,
        }

        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"Saved {total_words} words ({len(segments_data)} segments) to {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Transcribe Darija speech with word timestamps")
    parser.add_argument("--input", "-i", required=True, help="Input media file path")
    parser.add_argument("--output", "-o", required=True, help="Output JSON transcript path")
    parser.add_argument("--model", "-m", default="small", help="Whisper model size (default: small)")
    parser.add_argument("--language", "-l", default="ar", help="Spoken language code (default: ar)")
    parser.add_argument("--device", "-d", default="auto", help="Compute device (auto, cpu, cuda)")
    args = parser.parse_args()

    transcribe_file(
        args.input,
        args.output,
        model_size=args.model,
        language=args.language,
        device=args.device,
    )


if __name__ == "__main__":
    main()
