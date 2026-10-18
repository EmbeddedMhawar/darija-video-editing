# Darija Video Editing Suite (Antigravity Plugin)

An end-to-end video editing pipeline specifically engineered for Moroccan Darija (الدارجة المغربية) mobile footage in **Storyteller FilmCraft**.

## Features

- **Resilient Mobile Ingestion (`scripts/mtp_ingest.py`)**: Seamlessly mounts and transfers 40+ GB takes over MTP with smart byte-level chunk resumption so interrupted transfers never start over.
- **Featherweight Timeline Proxies (`scripts/generate_proxies.py`)**: Generates 960×720 zero-B-frame (`-bf 0`) fastdecode proxies that scrub at **138+ fps** in FilmCraft while saving **>96% disk space**.
- **Darija Whisper Speech Recognition (`scripts/darija_transcribe.py`)**: Extracts word-level timestamped transcripts using `faster-whisper` (`--language ar`).
- **Safe Stdin FilmCraft Orchestrator (`scripts/filmcraft_pipeline.py`)**: Initializes projects, imports footage, lays out chronological timelines, binds proxies, and streams large transcript payloads via `stdin` to completely prevent Linux `ARG_MAX` buffer overflow.
- **YouTube Shorts Growth Funnel**: Bridges long-form master edits directly into 9:16 vertical Shorts with YouTube "Related Video" funneling for channel growth.

## Quick Start

```bash
# Ingest footage from phone
python3 scripts/mtp_ingest.py --dst "/path/to/raw_footage" --pattern "*.mov"

# Generate 960x720 lightweight proxies
python3 scripts/generate_proxies.py -i "/path/to/raw_footage" -o "/path/to/proxies"

# Initialize & assemble FilmCraft project
python3 scripts/filmcraft_pipeline.py init --project "/path/to/Project.fcproj"
python3 scripts/filmcraft_pipeline.py import --project "/path/to/Project.fcproj" --media "/path/to/raw_footage"
python3 scripts/filmcraft_pipeline.py assemble --project "/path/to/Project.fcproj"
python3 scripts/filmcraft_pipeline.py attach-proxies --project "/path/to/Project.fcproj" --proxies-dir "/path/to/proxies"
python3 scripts/filmcraft_pipeline.py attach-transcripts --project "/path/to/Project.fcproj" --transcripts-dir "/path/to/transcripts"
```
