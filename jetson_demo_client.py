#!/usr/bin/env python3
"""Arms a Jetson to start tactile playback on the demo server's next cue."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


def get_status(server_url: str) -> dict:
    with urlopen(f"{server_url.rstrip('/')}/api/playback/status", timeout=2) as response:  # nosec B310: user chooses local demo server
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description="Start Jetson tactile playback from a shared cue")
    parser.add_argument("--server", required=True, help="e.g. http://192.168.1.20:8000")
    parser.add_argument("--video", required=True, help="path to the same original clip on this Jetson")
    parser.add_argument("--name", default="demo", help="saved calibration/trajectory name")
    parser.add_argument("--trajectory", help="optional explicit trajectory JSON")
    parser.add_argument("--mock-hardware", action="store_true", help="test without GPIO")
    parser.add_argument("--poll-seconds", type=float, default=0.2)
    args = parser.parse_args()

    last_run_id = 0
    project_root = Path(__file__).resolve().parent
    print("Jetson armed. Waiting for a browser cue…")
    while True:
        try:
            status = get_status(args.server)
            run_id = int(status["run_id"])
            start_at = status.get("start_at")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            print(f"Waiting for demo server ({error})", file=sys.stderr)
            time.sleep(args.poll_seconds)
            continue

        if run_id <= last_run_id or start_at is None:
            time.sleep(args.poll_seconds)
            continue

        last_run_id = run_id
        command = [
            sys.executable,
            str(project_root / "main.py"),
            "--video", args.video,
            "--name", args.name,
            "--start-at", str(start_at),
        ]
        if args.trajectory:
            command.extend(["--trajectory", args.trajectory])
        command.append("--mock-hardware" if args.mock_hardware else "--hardware")
        print(f"Cue {run_id}: tactile playback starts at {start_at:.3f}")
        subprocess.run(command, cwd=project_root, check=False)


if __name__ == "__main__":
    main()
