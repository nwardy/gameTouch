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
import time

from fan_pulse import load_local_env

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


def do_calibrate(video, name, sport):
    frame = video.first_frame()
    if frame is None:
        sys.exit("could not read first frame for calibration")
    homography = calibrate_from_frame(frame, sport)
    if homography is None:
        sys.exit("calibration aborted")
    calibration = CalibrationTimeline.single(homography)
    save_calibration(calibration, name)
    return calibration


def do_calibrate_shift(video, calibration, name, sport):
    """Mark one settled camera shift, then calibrate that second viewpoint."""
    print("Find the first stable frame after the camera view shifts, then ENTER.")
    shift_frame = choose_shift_frame(video)
    if shift_frame is None:
        sys.exit("camera-shift calibration aborted")
    shift_time = video.frame_to_time(shift_frame)
    frame = video.read_frame(shift_frame)
    print(f"Calibrating the post-shift view at t={shift_time:.2f}s.")
    homography = calibrate_from_frame(frame, sport)
    if homography is None:
        sys.exit("post-shift calibration aborted")
    calibration.add_shift(shift_time, homography)
    save_calibration(calibration, name)
    return calibration


def do_track(video, homography, name, every_frame=False, full_resolution=False):
    from tracking.ball_tracker import track_clip, select_initial_box

    frame = video.first_frame()
    box = select_initial_box(frame)
    if box is None:
        sys.exit("no ball box selected")
    print("Tracking... (this runs once, offline)")
    points = track_clip(
        video, homography, box,
        every_n=1 if every_frame else 2,
        process_width=video.width if full_resolution else 640,
    )
    if not points:
        sys.exit("tracking produced no points")
    source = PrerecordedSource(points)
    source.save(trajectory_path(name))
    print(f"Saved trajectory ({len(points)} points) -> {trajectory_path(name)}")
    return source


def do_manual_path(video, homography, name, resume=False, sport="soccer"):
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
    points = annotate_manual_path(video, homography, initial_points=existing_points,
                                  sport=sport)
    if not points:
        sys.exit("no manual ball points saved")
    source = PrerecordedSource(points)
    source.save(trajectory_path(name))
    print(f"Saved manual trajectory ({len(points)} points) -> {trajectory_path(name)}")
    return source


def write_birdseye_video(video_path, source, output_path, speed, sport):
    """Render a shareable top-down MP4 from a saved or newly tracked path."""
    from video.birdseye_renderer import render_birdseye_video

    render_video = VideoLoader(video_path)
    try:
        saved_path = render_birdseye_video(
            render_video, source, output_path, speed=speed, sport=sport,
        )
    finally:
        render_video.release()
    print(f"Saved bird's-eye video -> {saved_path}")


def main():
    load_local_env()
    ap = argparse.ArgumentParser(description="Tactile sports-field system")
    ap.add_argument("--video", required=True, help="path to input video")
    ap.add_argument("--name", default="default",
                    help="identifier tying calibration + trajectory together")
    ap.add_argument("--sport", choices=("soccer", "tennis", "tennis-singles"), default="soccer",
                    help="field template and calibration dimensions (default: soccer)")
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
    ap.add_argument("--track-every-frame", action="store_true",
                    help="do not skip frames; recommended for a fast tennis ball")
    ap.add_argument("--track-full-resolution", action="store_true",
                    help="do not downscale frames before tracking; slower but preserves tiny balls")
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
    ap.add_argument("--start-at", type=float,
                    help="Unix timestamp for a coordinated replay start (demo use)")
    ap.add_argument("--fan-query",
                    help="X search terms for live fan context, e.g. '#GTvsUGA'")
    ap.add_argument("--fan-pulse-interval", type=int, default=90,
                    help="deprecated; fan pulse refreshes only when requested")
    ap.add_argument("--fan-button-pin", type=int,
                    help="optional Jetson BOARD pin for a momentary fan-pulse button")
    args = ap.parse_args()

    video = VideoLoader(args.video)

    # -- calibration -------------------------------------------------------
    homography = load_calibration(args.name)
    if args.calibrate or homography is None:
        if not args.calibrate:
            print(f"No saved calibration '{args.name}'. Launching calibration.")
        homography = do_calibrate(video, args.name, args.sport)

    if args.calibrate_shift:
        homography = do_calibrate_shift(video, homography, args.name, args.sport)

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
            resume=args.resume_manual_path, sport=args.sport,
        )
    elif args.track:
        source = do_track(
            video, runtime_calibration, args.name,
            every_frame=args.track_every_frame,
            full_resolution=args.track_full_resolution,
        )
    else:
        try:
            source = PrerecordedSource.from_name(args.name)
        except FileNotFoundError:
            print(f"No trajectory '{args.name}'. Run with --track first.")
            source = do_track(
                video, runtime_calibration, args.name,
                every_frame=args.track_every_frame,
                full_resolution=args.track_full_resolution,
            )

    if args.birdseye_output:
        write_birdseye_video(
            args.video,
            source,
            args.birdseye_output,
            speed=args.birdseye_speed,
            sport=args.sport,
        )

    # -- output sink -------------------------------------------------------
    output = build_output(hardware_mode=args.hardware)
    output.setup()

    # -- playback (safe shutdown guarantees relays end OFF) ----------------
    from video.playback import play  # imported late so cv2 GUI loads on demand
    fan_pulse = None
    fan_button = None
    if args.fan_query:
        from fan_pulse import FanPulseService

        def announce_fan_pulse(pulse):
            """Expose each new summary to terminal screen readers and adapters."""
            if pulse.intensity is None:
                print(f"\nFAN PULSE: {pulse.text}")
                return
            print(f"\nLIVE GAME CONTEXT: {pulse.game_context}")
            print(
                f"SOCCER EVENT: {pulse.event.replace('_', ' ') if pulse.event else 'none'} "
                f"({pulse.event_confidence or 'low'} confidence)"
            )
            print(
                f"FAN PULSE ({pulse.sampled_posts} X posts, {pulse.intensity}/100 "
                f"{pulse.level}): {pulse.text}"
            )

        fan_pulse = FanPulseService(
            args.fan_query, args.fan_pulse_interval, on_update=announce_fan_pulse
        )
        fan_pulse.start()
        if args.fan_button_pin:
            if not args.hardware:
                sys.exit("--fan-button-pin requires --hardware on a Jetson.")
            from tactile.fan_pulse_button import FanPulseButton
            fan_button = FanPulseButton(args.fan_button_pin, fan_pulse.request_refresh)
            fan_button.start()
            print(f"Fan button ready on BOARD pin {args.fan_button_pin}.")
        print("Fan pulse ready. Press F in the video window, or the configured board button.")

    # Restart video for sequential playback (tracking may have seeked around).
    video.release()
    video = VideoLoader(args.video)
    if not args.static_grid:
        from calibration.adaptive_calibration import AdaptiveCalibration
        runtime_calibration = AdaptiveCalibration(video, homography)
    if args.start_at is not None:
        remaining = args.start_at - time.time()
        if remaining > 0:
            print(f"Armed for coordinated start in {remaining:.2f}s.")
            time.sleep(remaining)
        elif remaining < -0.5:
            print(f"WARNING: start cue arrived {abs(remaining):.2f}s late; playing immediately.")
    try:
        play(video, source, output, calibration=runtime_calibration, fan_pulse=fan_pulse,
             debug=not args.no_debug, sport=args.sport)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        output.all_off()
        output.cleanup()
        video.release()
        if fan_pulse:
            fan_pulse.stop()
        if fan_button:
            fan_button.cleanup()


if __name__ == "__main__":
    main()
