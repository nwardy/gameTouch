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
    choose_shift_frame,
    load_calibration,
    save_calibration,
)
from calibration.calibration_timeline import CalibrationTimeline


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
    homography = calibrate_from_frame(frame)
    if homography is None:
        sys.exit("calibration aborted")
    calibration = CalibrationTimeline.single(homography)
    save_calibration(calibration, name)
    return calibration


def do_calibrate_shift(video, calibration, name):
    """Mark one settled camera shift, then calibrate that second viewpoint."""
    print("Find the first stable frame after the camera view shifts, then ENTER.")
    shift_frame = choose_shift_frame(video)
    if shift_frame is None:
        sys.exit("camera-shift calibration aborted")
    shift_time = video.frame_to_time(shift_frame)
    frame = video.read_frame(shift_frame)
    print(f"Calibrating the post-shift view at t={shift_time:.2f}s.")
    homography = calibrate_from_frame(frame)
    if homography is None:
        sys.exit("post-shift calibration aborted")
    calibration.add_shift(shift_time, homography)
    save_calibration(calibration, name)
    return calibration


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


def do_manual_path(video, homography, name, resume=False):
    """Collect a precise timestamped path when the ball is too small to track."""
    from tracking.manual_path import annotate_manual_path

    existing_points = None
    if resume:
        try:
            existing_points = PrerecordedSource.from_name(name).points
            print(f"Resuming {len(existing_points)} saved manual points.")
        except FileNotFoundError:
            print("No saved trajectory to resume; starting a new manual path.")
    print("Manual path mode: click the ball while paused or playing; ENTER saves.")
    points = annotate_manual_path(video, homography, initial_points=existing_points)
    if not points:
        sys.exit("no manual ball points saved")
    source = PrerecordedSource(points)
    source.save(trajectory_path(name))
    print(f"Saved manual trajectory ({len(points)} points) -> {trajectory_path(name)}")
    return source


def write_birdseye_video(video_path, source, output_path, speed):
    """Render a shareable top-down MP4 from a saved or newly tracked path."""
    from video.birdseye_renderer import render_birdseye_video

    render_video = VideoLoader(video_path)
    try:
        saved_path = render_birdseye_video(render_video, source, output_path, speed=speed)
    finally:
        render_video.release()
    print(f"Saved bird's-eye video -> {saved_path}")


def main():
    ap = argparse.ArgumentParser(description="Tactile sports-field system")
    ap.add_argument("--video", required=True, help="path to input video")
    ap.add_argument("--name", default="default",
                    help="identifier tying calibration + trajectory together")
    ap.add_argument("--trajectory", help="explicit trajectory JSON (skips --track)")
    ap.add_argument("--calibrate", action="store_true",
                    help="calibrate visible pitch landmarks and save the mapping")
    ap.add_argument("--calibrate-shift", action="store_true",
                    help="mark one settled camera shift and calibrate the new view")
    ap.add_argument("--static-grid", action="store_true",
                    help="disable automatic small camera-motion adjustment")
    ap.add_argument("--calibrate-only", action="store_true",
                    help="save calibration and exit without tracking or playback")
    ap.add_argument("--track", action="store_true",
                    help="generate a trajectory by tracking the ball")
    ap.add_argument("--manual-path", action="store_true",
                    help="click a timestamped ball path when automatic tracking is unreliable")
    ap.add_argument("--resume-manual-path", action="store_true",
                    help="keep the saved manual path and add/correct points")
    ap.add_argument("--hardware", action="store_true",
                    help="drive real Jetson relay hardware")
    ap.add_argument("--mock-hardware", action="store_true",
                    help="use the console mock output (default on MacBook)")
    ap.add_argument("--no-debug", action="store_true",
                    help="disable the on-screen debug overlay")
    ap.add_argument("--birdseye-output",
                    help="write a top-down soccer-pitch MP4 to this path")
    ap.add_argument("--birdseye-speed", type=float, default=1.0,
                    help="bird's-eye MP4 playback speed; 0.25 is quarter speed")
    ap.add_argument("--fan-query",
                    help="X search terms for live fan context, e.g. '#GTvsUGA'")
    ap.add_argument("--fan-pulse-interval", type=int, default=90,
                    help="seconds between fan-pulse refreshes (default: 90)")
    args = ap.parse_args()

    video = VideoLoader(args.video)

    # -- calibration -------------------------------------------------------
    homography = load_calibration(args.name)
    if args.calibrate or homography is None:
        if not args.calibrate:
            print(f"No saved calibration '{args.name}'. Launching calibration.")
        homography = do_calibrate(video, args.name)

    if args.calibrate_shift:
        homography = do_calibrate_shift(video, homography, args.name)

    if args.calibrate_only:
        video.release()
        return

    # The saved landmarks become lightweight visual anchors for small motion.
    # This never changes the saved calibration and safely falls back to it.
    if not args.static_grid:
        from calibration.adaptive_calibration import AdaptiveCalibration
        runtime_calibration = AdaptiveCalibration(video, homography)
    else:
        runtime_calibration = homography

    # -- trajectory (position source) --------------------------------------
    if args.trajectory:
        source = PrerecordedSource.from_file(args.trajectory)
    elif args.manual_path:
        source = do_manual_path(
            video, runtime_calibration, args.name,
            resume=args.resume_manual_path,
        )
    elif args.track:
        source = do_track(video, runtime_calibration, args.name)
    else:
        try:
            source = PrerecordedSource.from_name(args.name)
        except FileNotFoundError:
            print(f"No trajectory '{args.name}'. Run with --track first.")
            source = do_track(video, runtime_calibration, args.name)

    if args.birdseye_output:
        write_birdseye_video(
            args.video,
            source,
            args.birdseye_output,
            speed=args.birdseye_speed,
        )

    # -- output sink -------------------------------------------------------
    output = build_output(hardware_mode=args.hardware)
    output.setup()

    # -- playback (safe shutdown guarantees relays end OFF) ----------------
    from video.playback import play  # imported late so cv2 GUI loads on demand
    fan_pulse = None
    if args.fan_query:
        from fan_pulse import FanPulseService

        def announce_fan_pulse(pulse):
            """Expose each new summary to terminal screen readers and adapters."""
            print(f"\nFAN PULSE ({pulse.sampled_posts} sampled posts): {pulse.text}")

        fan_pulse = FanPulseService(
            args.fan_query, args.fan_pulse_interval, on_update=announce_fan_pulse
        )
        fan_pulse.start()

    # Restart video for sequential playback (tracking may have seeked around).
    video.release()
    video = VideoLoader(args.video)
    if not args.static_grid:
        from calibration.adaptive_calibration import AdaptiveCalibration
        runtime_calibration = AdaptiveCalibration(video, homography)
    try:
        play(video, source, output, calibration=runtime_calibration, fan_pulse=fan_pulse,
             debug=not args.no_debug)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        output.all_off()
        output.cleanup()
        video.release()
        if fan_pulse:
            fan_pulse.stop()


if __name__ == "__main__":
    main()
