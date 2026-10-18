---
name: darija-video-editing
description: End-to-end video editing pipeline tailored for Moroccan Darija footage in FilmCraft: mobile MTP ingestion with chunk resumption, featherweight zero-lag editing proxies (960x720, -bf 0), faster-whisper Arabic/Darija word-level transcription with stdin-streamed timestamp injection, chronological master timeline assembly, and YouTube long-form to Shorts spin-off funnels.
---

# Darija Video Editing Suite (darija-video-editing)

Comprehensive pipeline tailored for high-bitrate mobile camera footage (MotionCam Pro / Android / Open Gate) speaking **Moroccan Darija (الدارجة المغربية)** and edited in **Storyteller FilmCraft**.

Solves the four critical hurdles of Darija mobile video production:
1. **MTP Bus Stalls & Disconnections**: Resilient sequential file pulling with chunk-level byte append resumption.
2. **Machine Playback Lag & Disk Bloat**: Ultra-compact 960×720 intra-friendly editing proxies (`-bf 0`, `-tune fastdecode`) decoding at **138+ fps** while saving **>96% disk space**.
3. **FilmCraft Language Mismatch**: Replaces English-default transcription with `faster-whisper` (`--language ar`), safely streaming word timestamps via `stdin` to bypass Linux `ARG_MAX` ceilings.
4. **YouTube Growth Synergy**: Structures long-form master storytelling first, then spins off high-retention 9:16 vertical Shorts linked directly via YouTube "Related Video" funnels.

---

## 5-Phase Operating Protocol

```
[Phone (MTP)] ──> Step 1: mtp_ingest.py ──> [Raw Footage]
                       │
                       ├──> Step 2: generate_proxies.py ──> [960x720 Proxies (~1.5GB)]
                       │
                       ├──> Step 3: darija_transcribe.py ──> [Word Timestamps]
                       │
                       └──> Step 4: filmcraft_pipeline.py ──> [LongForm_Fisik101.fcproj]
                                                                     │
                                                       (Approved Master Cut)
                                                                     │
                                                       Step 5: 9:16 Shorts Funnel
```

---

### Phase 1: Mobile & MTP Resilient Ingestion

Mobile camera footage (e.g. MotionCam Pro 4K/UHD open gate) generates 40–100 GB files over USB. Standard GVFS/MTP GUI copies crash or freeze on long transfers.

Run the resilient sequential ingestion tool:

```bash
python3 scripts/mtp_ingest.py \
  --dst "/path/to/project/raw_footage" \
  --pattern "*.mov" \
  --date "YYMMDD"
```

* **Smart Chunk Resumption**: If a 10 GB file is interrupted halfway, the engine reads the existing byte count on disk, seeks to that exact offset, and appends the remaining chunks without re-downloading earlier gigabytes.
* **Sequential Threading**: Enforces strict single-file transfers to prevent MTP protocol pipe collisions.

---

### Phase 2: Featherweight Editing Proxies (Disk & CPU Friendly)

Raw 4000×3008 footage drops below realtime playback on standard CPUs (~18 fps). These proxies deliver instant, zero-lag timeline scrubbing while consuming less than 4% of original disk space:

```bash
python3 scripts/generate_proxies.py \
  --input "/path/to/project/raw_footage" \
  --output-dir "/path/to/project/proxies" \
  --width 960 \
  --crf 24
```

* **Specifications**:
  * **Scale**: `960×720` (exact 4:3) or `960×540` (16:9).
  * **Zero B-Frames (`-bf 0`) & GOP 60**: Instant frame seek with zero predictive inter-frame decode lag.
  * **Fastdecode Tuning (`-tune fastdecode`)**: Disables high-complexity CABAC and in-loop deblocking; decodes at **138+ fps** in FilmCraft.
  * **Audio Pass-Through (`-c:a copy`)**: Bit-for-bit lossless copy of the original 48 kHz stereo audio, preserving clean waveforms and dialogue sync on Track A1.
  * **Disk Footprint**: ~1.5 GB total for over 1 hour of 4K footage (>96% space saved).

---

### Phase 3: Moroccan Darija Speech Recognition & Native FilmCraft Injection

FilmCraft's native auto-transcribe defaults to English (`"defaultLanguage": "en"`). Use the Darija transcription engine to extract word-level timestamps:

```bash
uv run --python 3.12 --with "faster-whisper" --with "av<14" python3 \
  scripts/darija_transcribe.py \
  --input "/path/to/clip.mov" \
  --output "/path/to/transcripts/clip.json" \
  --model small \
  --language ar
```

#### Safe Stdin Transcript Injection (Bypassing `ARG_MAX`)
Long clips (>5 minutes) produce thousands of timestamped words. Passing them via command-line strings causes `OSError: [Errno 7] Argument list too long`.

Always stream the JSON command payload via `stdin` using `filmcraft-cli run -`:

```python
import json, subprocess
TICKS_PER_SEC = 254016000000

cmd_obj = {
    "id": "transcript.set",
    "params": {
        "item": item_id,
        "transcript": {
            "language": "ar",
            "speakers": [{"name": "Speaker 1"}],
            "words": [
                {
                    "text": w["word"],
                    "start": int(round(w["start"] * TICKS_PER_SEC)),
                    "end": int(round(w["end"] * TICKS_PER_SEC)),
                    "speaker": 0
                }
                for w in words_data
            ]
        }
    }
}

subprocess.run(
    ["filmcraft-cli", "--project", "project.fcproj", "--save", "run", "-"],
    input=json.dumps(cmd_obj) + "\n",
    text=True
)
```

---

### Phase 4: Long-Form Timeline Master Assembly

Orchestrate the entire FilmCraft project and timeline with a single command suite:

```bash
# 1. Initialize master 4K sequence (V1-V3, A1-A3)
python3 scripts/filmcraft_pipeline.py init \
  --project "/path/to/LongForm_Fisik101.fcproj" \
  --sequence-name "Master Assembly" \
  --width 3840 --height 2160 --fps 24.0

# 2. Batch import all raw footage
python3 scripts/filmcraft_pipeline.py import \
  --project "/path/to/LongForm_Fisik101.fcproj" \
  --media "/path/to/raw_footage"

# 3. Assemble clips chronologically onto Track V1 / A1
python3 scripts/filmcraft_pipeline.py assemble \
  --project "/path/to/LongForm_Fisik101.fcproj"

# 4. Attach generated proxies to all items
python3 scripts/filmcraft_pipeline.py attach-proxies \
  --project "/path/to/LongForm_Fisik101.fcproj" \
  --proxies-dir "/path/to/proxies"

# 5. Inject Darija transcripts to all items
python3 scripts/filmcraft_pipeline.py attach-transcripts \
  --project "/path/to/LongForm_Fisik101.fcproj" \
  --transcripts-dir "/path/to/transcripts"
```

#### Global Preference Setting
Ensure FilmCraft automatically defaults to proxy playback upon startup by confirming `~/.local/share/filmcraft/preferences.json`:
```json
"enableProxies": true
```

---

### Phase 5: YouTube Growth & Shorts Spin-off Funnel (@fisik101)

Once the long-form master cut is polished and approved:

1. **Strategic Posting Cadence**:
   * **Long-Form**: 1 to 2 videos per week (48–72 hours between uploads to let Browse & Suggested algorithms index).
   * **Shorts**: 2 to 3 Shorts per day, spaced **3 to 4 hours apart** (e.g., 13:00, 17:00, 21:00 GMT+1).
2. **The Related Video Funnel**:
   * For every Short extracted from the long-form master, set the **"Related Video"** link in YouTube Studio to the parent long-form video.
   * Converts high-volume Shorts views directly into long-form watch time and channel subscribers.
3. **Short-Form Canvas & Styling**:
   * 9:16 vertical canvas (1080×1920).
   * High-contrast kinetic captions in mic/chest safe zone (`margin_v: ~420px`).
   * Hook $\rightarrow$ Story $\rightarrow$ Payoff structure (dead air $>0.4$s excised with 80 ms consonant protection buffer).
