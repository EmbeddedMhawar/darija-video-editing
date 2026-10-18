#!/usr/bin/env python3
"""
mtp_ingest.py

Resilient MTP mobile ingestion engine with smart chunk resumption.
Designed for high-bitrate mobile footage (MotionCam Pro / Android).
Transfers files sequentially over MTP to prevent USB bus stalls.
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def mount_mtp_device() -> str:
    """Detect and mount connected Android/MTP phone if not already mounted."""
    res = subprocess.run(["gio", "mount", "-li"], capture_output=True, text=True)
    mount_root = None
    for line in res.stdout.splitlines():
        if "activation_root=mtp://" in line:
            mount_root = line.split("activation_root=")[-1].strip()
            break

    if mount_root:
        subprocess.run(["gio", "mount", mount_root], capture_output=True)

    uid = os.getuid()
    gvfs_dir = Path(f"/run/user/{uid}/gvfs")
    if gvfs_dir.exists():
        for d in gvfs_dir.iterdir():
            if d.name.startswith("mtp:"):
                # Check for standard DCIM/MotionCam path
                dcim = d / "Internal shared storage" / "DCIM" / "MotionCam"
                if dcim.exists():
                    return str(dcim)
                dcim_std = d / "Internal shared storage" / "DCIM"
                if dcim_std.exists():
                    return str(dcim_std)
                return str(d)
    return None


def resume_append(src: Path, dst: Path, src_size: int, dst_size: int, chunk_mb: int = 8) -> bool:
    """Resume a partial file by seeking and appending missing chunks."""
    print(f"  Resuming append from {dst_size / (1024**2):.1f} MB to {src_size / (1024**2):.1f} MB...", flush=True)
    t0 = time.time()
    chunk_size = chunk_mb * 1024 * 1024
    with open(src, "rb") as fsrc, open(dst, "ab") as fdst:
        fsrc.seek(dst_size)
        copied = 0
        target = src_size - dst_size
        while copied < target:
            to_read = min(chunk_size, target - copied)
            chunk = fsrc.read(to_read)
            if not chunk:
                break
            fdst.write(chunk)
            copied += len(chunk)
            if copied % (64 * 1024 * 1024) < chunk_size:
                curr = (dst_size + copied) / (1024**2)
                tot = src_size / (1024**2)
                pct = (dst_size + copied) / src_size * 100
                print(f"    Progress: {curr:.1f} / {tot:.1f} MB ({pct:.1f}%)", flush=True)
    elapsed = max(time.time() - t0, 0.001)
    speed = (copied / (1024**2)) / elapsed
    print(f"  Append complete in {elapsed:.1f}s ({speed:.1f} MB/s)", flush=True)
    return dst.stat().st_size == src_size


def ingest_files(src_dir: str, dst_dir: str, pattern: str = "*", date_filter: str = None):
    src_path = Path(src_dir).resolve()
    dst_path = Path(dst_dir).resolve()
    dst_path.mkdir(parents=True, exist_ok=True)

    files = sorted(src_path.glob(pattern))
    if date_filter:
        files = [f for f in files if date_filter in f.name]

    if not files:
        print(f"No matching files found in {src_path} (pattern: {pattern}, date: {date_filter})")
        return

    total_files = len(files)
    total_bytes = sum(f.stat().st_size for f in files)
    print(f"Found {total_files} files ({total_bytes / (1024**3):.2f} GB) to ingest into {dst_path}\n")

    for idx, src in enumerate(files, 1):
        filename = src.name
        dst = dst_path / filename
        src_size = src.stat().st_size
        dst_size = dst.stat().st_size if dst.exists() else 0

        if dst_size == src_size:
            print(f"[{idx}/{total_files}] Already complete: {filename} ({src_size / (1024**2):.1f} MB)")
            continue

        if 0 < dst_size < src_size:
            print(f"[{idx}/{total_files}] Partial file detected: {filename} ({dst_size / (1024**2):.1f} / {src_size / (1024**2):.1f} MB)")
            ok = resume_append(src, dst, src_size, dst_size)
            if ok:
                continue
            print("  Append mismatch, re-copying full file...")
            dst.unlink(missing_ok=True)

        print(f"[{idx}/{total_files}] Copying {filename} ({src_size / (1024**2):.1f} MB)...", flush=True)
        t0 = time.time()
        res = subprocess.run(["gio", "copy", str(src), str(dst)], capture_output=True, text=True)
        elapsed = max(time.time() - t0, 0.001)

        if res.returncode != 0:
            print(f"  Error copying {filename}: {res.stderr.strip()}", file=sys.stderr)
        else:
            speed = (src_size / (1024**2)) / elapsed
            print(f"  Done in {elapsed:.1f}s ({speed:.1f} MB/s)", flush=True)

    print("\nIngestion run complete.")


def main():
    parser = argparse.ArgumentParser(description="Resilient MTP mobile footage ingestion")
    parser.add_argument("--src", help="Source folder path (defaults to auto-detected MTP)")
    parser.add_argument("--dst", required=True, help="Destination folder path")
    parser.add_argument("--pattern", default="*.mov", help="File pattern (default: *.mov)")
    parser.add_argument("--date", help="Optional date prefix filter (e.g. 261018)")
    args = parser.parse_args()

    src = args.src
    if not src:
        src = mount_mtp_device()
        if not src:
            sys.exit("Error: Could not auto-detect mounted MTP phone. Provide --src explicitly.")
        print(f"Auto-detected MTP source: {src}")

    ingest_files(src, args.dst, args.pattern, args.date)


if __name__ == "__main__":
    main()
