#!/usr/bin/env python3
"""
Tactile sports-field system - entry point.

Typical workflows
-----------------
1. Calibrate the field once for a given camera view:
       python3 main.py --video input.mp4 --calibrate --name game1

2. Generate a ball trajectory from the clip (semi-manual: drag a box on the
   ball, tracker takes over):
       python3 main.py --video input.mp4 --track --name game1

3. Play back with tactile output (mock hardware on a MacBook):
       python3 main.py --video input.mp4 --name game1 --mock-hardware

4. On the Jetson, drive real relays:
       sudo python3 main.py --video input.mp4 --name game1 --hardware

The name ties together the saved calibration and trajectory for a clip. If you
already have a trajectory JSON you can pass --trajectory <path> directly and
skip tracking entirely (positions can come from anywhere).
"""

import argparse
import sys

from video.video_loader import VideoLoader
from tracking.prerecorded_source import PrerecordedSource, trajectory_path
from calibration.field_calibration import (
    calibrate_from_frame,
    load_calibration,
)


def build_output(hardware_mode):
    """Dependency injection point: pick the tactile sink for this platform."""
    if hardware_mode:
        from tactile.tactile_output import JetsonRelayTactileOutput
        return JetsonRelayTactileOutput()
    from tactile.mock_output import MockTactileOutput
    return MockTactileOutput()


def do_calibrate(video, name):
    frame = video.first_frame()
    if frame is None:
        sys.exit("could not read first frame for calibration")
    homography = calibrate_from_frame(frame, name=name)
    if homography is None:
        sys.exit("calibration aborted")
    return homography


def do_track(video, homography, name):
    from tracking.ball_tracker import track_clip, select_initial_box

    frame = video.first_frame()
    box = select_initial_box(frame)
    if box is None:
        sys.exit("no ball box selected")
    print("Tracking... (this runs once, offline)")
    points = track_clip(video, homography, box)
    if not points:
        sys.exit("tracking produced no points")
    source = PrerecordedSource(points)
    source.save(trajectory_path(name))
    print(f"Saved trajectory ({len(points)} points) -> {trajectory_path(name)}")
    return source


def main():
    ap = argparse.ArgumentParser(description="Tactile sports-field system")
    ap.add_argument("--video", required=True, help="path to input video")
    ap.add_argument("--name", default="default",
                    help="identifier tying calibration + trajectory together")
    ap.add_argument("--trajectory", help="explicit trajectory JSON (skips --track)")
    ap.add_argument("--calibrate", action="store_true",
                    help="run interactive corner calibration and save it")
    ap.add_argument("--track", action="store_true",
                    help="generate a trajectory by tracking the ball")
    ap.add_argument("--hardware", action="store_true",
                    help="drive real Jetson relay hardware")
    ap.add_argument("--mock-hardware", action="store_true",
                    help="use the console mock output (default on MacBook)")
    ap.add_argument("--no-debug", action="store_true",
                    help="disable the on-screen debug overlay")
    args = ap.parse_args()

    video = VideoLoader(args.video)

    # -- calibration -------------------------------------------------------
    homography = load_calibration(args.name)
    if args.calibrate or homography is None:
        if not args.calibrate:
            print(f"No saved calibration '{args.name}'. Launching calibration.")
        homography = do_calibrate(video, args.name)

    # -- trajectory (position source) --------------------------------------
    if args.trajectory:
        source = PrerecordedSource.from_file(args.trajectory)
    elif args.track:
        source = do_track(video, homography, args.name)
    else:
        try:
            source = PrerecordedSource.from_name(args.name)
        except FileNotFoundError:
            print(f"No trajectory '{args.name}'. Run with --track first.")
            source = do_track(video, homography, args.name)

    # -- output sink -------------------------------------------------------
    output = build_output(hardware_mode=args.hardware)
    output.setup()

    # -- playback (safe shutdown guarantees relays end OFF) ----------------
    from video.playback import play  # imported late so cv2 GUI loads on demand

    # Restart video for sequential playback (tracking may have seeked around).
    video.release()
    video = VideoLoader(args.video)
    try:
        play(video, source, output, homography=homography,
             debug=not args.no_debug)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        output.all_off()
        output.cleanup()
        video.release()


if __name__ == "__main__":
    main()
