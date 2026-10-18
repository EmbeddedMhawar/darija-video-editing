#!/usr/bin/env python3
"""
filmcraft_pipeline.py

Master FilmCraft CLI orchestrator for the Darija video editing workflow:
- Project & sequence initialization
- Chronological timeline placement on Tracks V1/A1
- Proxy attachment (media.attachProxies)
- Safe transcript streaming via stdin (filmcraft-cli run -) to prevent ARG_MAX errors
- Project inspection & status auditing
"""

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

TICKS_PER_SEC = 254016000000
CLI_PATH = "/home/mhawar/.local/share/filmcraft/squashfs-root/usr/bin/filmcraft-cli"


def inspect_project(project_path: Path) -> dict:
    if not project_path.exists():
        return {}
    res = subprocess.run([CLI_PATH, "--project", str(project_path), "inspect", "project"], capture_output=True, text=True)
    if res.returncode != 0:
        return {}
    return json.loads(res.stdout)


def get_item_map(project_path: Path) -> dict:
    data = inspect_project(project_path)
    item_map = {}
    for child in data.get("root", {}).get("children", []):
        if child.get("name") and child.get("item"):
            item_map[child["name"]] = {
                "item": child["item"],
                "type": child.get("type"),
                "duration": child.get("duration", 0),
            }
    return item_map


def cmd_init(args):
    project_path = Path(args.project).resolve()
    project_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Initializing FilmCraft project at {project_path}...")
    cmd = [
        CLI_PATH,
        "--save-as", str(project_path),
        "exec", "file.newSequence",
        f"name={args.sequence_name}",
        f"width={args.width}",
        f"height={args.height}",
        f"fps={args.fps}",
        "video=3",
        "audio=3"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"Sequence '{args.sequence_name}' ({args.width}x{args.height} @ {args.fps}fps) initialized.")
    else:
        sys.exit(f"Failed to initialize sequence: {res.stderr}")


def cmd_import(args):
    project_path = Path(args.project).resolve()
    media_files = []
    for inp in args.media:
        p = Path(inp).resolve()
        if p.is_dir():
            for ext in [".mov", ".mp4", ".mkv", ".MOV", ".MP4"]:
                media_files.extend(sorted(p.glob(f"*{ext}")))
        elif p.is_file():
            media_files.append(p)

    unique_files = sorted(list({f.resolve(): f for f in media_files}.values()))
    if not unique_files:
        print("No media files found to import.")
        return

    print(f"Importing {len(unique_files)} media files into {project_path.name}...")
    cmd = [CLI_PATH, "--project", str(project_path), "--save", "import"] + [str(f) for f in unique_files]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        data = json.loads(res.stdout)
        print(f"Successfully imported {len(data.get('items', []))} items.")
    else:
        sys.exit(f"Import failed: {res.stderr}")


def cmd_assemble(args):
    project_path = Path(args.project).resolve()
    item_map = get_item_map(project_path)

    movies = []
    for name, info in item_map.items():
        if info.get("type") == "Movie":
            movies.append({"name": name, "item": info["item"], "duration": info["duration"]})

    movies.sort(key=lambda m: m["name"])
    if not movies:
        print("No Movie items found in project to assemble.")
        return

    print(f"Assembling {len(movies)} clips chronologically on Timeline (V1 / A1)...")
    commands = []
    curr_time = 0
    for m in movies:
        place_cmd = {
            "id": "timeline.place",
            "params": {
                "item": m["item"],
                "track": "V1",
                "audioTrack": "A1",
                "time": curr_time,
                "sourceIn": 0,
                "duration": m["duration"],
                "insert": False
            }
        }
        commands.append(json.dumps(place_cmd))
        curr_time += m["duration"]

    script_content = "\n".join(commands) + "\n"
    res = subprocess.run(
        [CLI_PATH, "--project", str(project_path), "--save", "run", "-"],
        input=script_content,
        text=True,
        capture_output=True
    )
    if res.returncode == 0:
        total_sec = curr_time / TICKS_PER_SEC
        print(f"Timeline assembled: {len(movies)} clips, total duration: {total_sec:.1f}s ({total_sec / 60:.2f} min).")
    else:
        sys.exit(f"Failed to place clips on timeline: {res.stderr}")


def cmd_attach_proxies(args):
    project_path = Path(args.project).resolve()
    proxies_dir = Path(args.proxies_dir).resolve()
    item_map = get_item_map(project_path)

    attached = 0
    for name, info in item_map.items():
        if info.get("type") != "Movie":
            continue
        proxy_file = proxies_dir / name
        if proxy_file.exists() and proxy_file.stat().st_size > 0:
            cmd_obj = {
                "id": "media.attachProxies",
                "params": {
                    "item": info["item"],
                    "path": str(proxy_file.resolve())
                }
            }
            res = subprocess.run(
                [CLI_PATH, "--project", str(project_path), "--save", "run", "-"],
                input=json.dumps(cmd_obj) + "\n",
                text=True,
                capture_output=True
            )
            if res.returncode == 0:
                attached += 1
                print(f"Attached proxy for {name} (item {info['item']})")

    print(f"Proxy attachment complete: {attached} clips linked.")


def cmd_attach_transcripts(args):
    project_path = Path(args.project).resolve()
    transcripts_dir = Path(args.transcripts_dir).resolve()
    item_map = get_item_map(project_path)

    attached = 0
    for name, info in item_map.items():
        if info.get("type") != "Movie":
            continue
        stem = Path(name).stem
        json_file = transcripts_dir / f"{stem}.json"
        if not json_file.exists():
            # Try full name suffix
            json_file = transcripts_dir / f"{name}.json"

        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as f:
                t_data = json.load(f)

            words = []
            for seg in t_data.get("segments", []):
                for w in seg.get("words", []):
                    words.append({
                        "text": w["word"],
                        "start": int(round(w["start"] * TICKS_PER_SEC)),
                        "end": int(round(w["end"] * TICKS_PER_SEC)),
                        "speaker": 0
                    })

            cmd_obj = {
                "id": "transcript.set",
                "params": {
                    "item": info["item"],
                    "transcript": {
                        "language": t_data.get("language", "ar"),
                        "speakers": [{"name": "Speaker 1"}],
                        "words": words
                    }
                }
            }

            # Safe stdin stream avoids Linux ARG_MAX limit
            res = subprocess.run(
                [CLI_PATH, "--project", str(project_path), "--save", "run", "-"],
                input=json.dumps(cmd_obj) + "\n",
                text=True,
                capture_output=True
            )
            if res.returncode == 0:
                attached += 1
                print(f"Attached {len(words)} words to {name} (item {info['item']})")
            else:
                print(f"Failed to attach transcript to {name}: {res.stderr}")

    print(f"Transcript attachment complete: {attached} clips synchronized.")


def cmd_status(args):
    project_path = Path(args.project).resolve()
    item_map = get_item_map(project_path)
    print(f"Project: {project_path.name} ({len(item_map)} total items)")

    # Check attached transcripts
    res_t = subprocess.run([CLI_PATH, "--project", str(project_path), "exec", "transcript.inspect"], capture_output=True, text=True)
    t_data = json.loads(res_t.stdout) if res_t.returncode == 0 else {}
    words_total = len(t_data.get("words", []))
    items_with_t = {itm.get("item"): itm for itm in t_data.get("items", [])}

    print(f"Timeline Words: {words_total}")
    for name, info in sorted(item_map.items()):
        dur = info.get("duration", 0) / TICKS_PER_SEC
        t_info = items_with_t.get(info["item"])
        w_count = t_info.get("words", 0) if t_info else 0
        print(f"  [{info['type']}] {name}: {dur:.1f}s | Transcript: {w_count} words")


def main():
    parser = argparse.ArgumentParser(description="Master FilmCraft pipeline orchestrator")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize project with sequence")
    p_init.add_argument("--project", required=True, help="Path to .fcproj")
    p_init.add_argument("--sequence-name", default="Master Assembly")
    p_init.add_argument("--width", type=int, default=3840)
    p_init.add_argument("--height", type=int, default=2160)
    p_init.add_argument("--fps", type=float, default=24.0)

    # import
    p_imp = subparsers.add_parser("import", help="Import media into project")
    p_imp.add_argument("--project", required=True)
    p_imp.add_argument("--media", required=True, nargs="+")

    # assemble
    p_ass = subparsers.add_parser("assemble", help="Assemble timeline chronologically")
    p_ass.add_argument("--project", required=True)

    # attach-proxies
    p_prx = subparsers.add_parser("attach-proxies", help="Attach proxy files to items")
    p_prx.add_argument("--project", required=True)
    p_prx.add_argument("--proxies-dir", required=True)

    # attach-transcripts
    p_trn = subparsers.add_parser("attach-transcripts", help="Attach word transcripts to items")
    p_trn.add_argument("--project", required=True)
    p_trn.add_argument("--transcripts-dir", required=True)

    # status
    p_st = subparsers.add_parser("status", help="Inspect project and timeline status")
    p_st.add_argument("--project", required=True)

    args = parser.parse_args()
    if args.subcommand == "init":
        cmd_init(args)
    elif args.subcommand == "import":
        cmd_import(args)
    elif args.subcommand == "assemble":
        cmd_assemble(args)
    elif args.subcommand == "attach-proxies":
        cmd_attach_proxies(args)
    elif args.subcommand == "attach-transcripts":
        cmd_attach_transcripts(args)
    elif args.subcommand == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
