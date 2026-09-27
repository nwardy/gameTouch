#!/usr/bin/env python3
"""Create browser-safe video assets from OpenCV-generated demo output.

OpenCV's default MP4 writer often produces FMP4, which plays in OpenCV but not
in Chromium. This converts the generated field-view replay to VP8/WebM for the
local presentation page while leaving the source artifact untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def convert(source_path: Path, destination_path: Path):
    source = cv2.VideoCapture(str(source_path))
    if not source.isOpened():
        raise FileNotFoundError(f"Could not open {source_path}")
    fps = source.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(source.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(source.get(cv2.CAP_PROP_FRAME_HEIGHT))
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(destination_path),
        cv2.VideoWriter_fourcc(*"VP80"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError("This OpenCV build cannot encode VP8/WebM.")
    frames = 0
    try:
        while True:
            ok, frame = source.read()
            if not ok:
                break
            writer.write(frame)
            frames += 1
    finally:
        source.release()
        writer.release()
    print(f"Converted {frames} frames: {source_path} -> {destination_path}")


def main():
    parser = argparse.ArgumentParser(description="Build FieldSense browser video assets")
    parser.add_argument("--source", type=Path, default=Path("data/outputs/v3goal.mp4"))
    parser.add_argument("--output", type=Path, default=Path("web/assets/field-view.webm"))
    args = parser.parse_args()
    convert(args.source, args.output)


if __name__ == "__main__":
    main()
