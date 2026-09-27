"""
Ball tracking / trajectory generation for prerecorded clips.

Design priorities (per project spec): be fast and simple, and lean on
semi-manual initialization rather than heavy inference. We only need to know
which of 20 large field regions the ball is in, so a lightweight OpenCV tracker
seeded by one manual box is plenty for V1. If it loses the ball, the user
clicks its center and tracking continues from that frame.

Output contains both normalized coordinates for the tactile grid and explicit
soccer-pitch coordinates (``x_meters``/``y_meters``) for analysis. The tracker
never talks to the tactile system directly, keeping vision and output loosely
coupled.
"""

import cv2
import numpy as np

from config import (
    FIELD_LENGTH_METERS,
    FIELD_WIDTH_METERS,
    PROCESS_WIDTH,
    PROCESS_EVERY_N_FRAMES,
    BALL_WHITE_MIN_PIXELS,
    BALL_WHITE_MAX_PIXELS,
    PLAYER_WHITE_COMPONENT_MIN_PIXELS,
    WHITE_PIXEL_MAX_SATURATION,
    WHITE_PIXEL_MIN_VALUE,
)


def _make_tracker():
    """Return an OpenCV single-object tracker, tolerant of version differences."""
    for factory in (
        getattr(cv2, "TrackerCSRT_create", None),
        getattr(getattr(cv2, "legacy", None), "TrackerCSRT_create", None),
        getattr(cv2, "TrackerKCF_create", None),
        getattr(getattr(cv2, "legacy", None), "TrackerKCF_create", None),
    ):
        if factory is not None:
            return factory()
    raise RuntimeError(
        "No OpenCV tracker available. Install opencv-contrib-python."
    )


def select_initial_box(frame, window="Select ball, then ENTER/SPACE"):
    """Let the user drag a box around the ball on the first frame."""
    box = cv2.selectROI(window, frame, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(window)
    if box == (0, 0, 0, 0):
        return None
    return box  # (x, y, w, h)


def track_clip(video, calibration, init_box, start_frame=0, end_frame=None,
               every_n=PROCESS_EVERY_N_FRAMES, process_width=PROCESS_WIDTH):
    """Track the ball across a frame range and return a normalized trajectory.

    Parameters
    ----------
    video        : VideoLoader (already opened)
    calibration  : CalibrationTimeline selecting pixels -> field by timestamp
    init_box     : (x, y, w, h) ball box on `start_frame`, in ORIGINAL pixels
    start_frame  : first frame of the play
    end_frame    : last frame (inclusive); None = to end of clip
    every_n      : run the tracker every Nth frame (skipped frames interpolate
                   naturally later via PrerecordedSource)
    process_width: downscale width for tracking speed

    Returns list of {time, x, y}. Coordinates are mapped back to original
    resolution before the homography, so scaling never distorts the result.
    """
    if end_frame is None:
        end_frame = video.frame_count - 1

    scale = process_width / video.width if video.width > process_width else 1.0

    tracker = _make_tracker()
    first = video.read_frame(start_frame)
    if first is None:
        raise RuntimeError(f"could not read start_frame {start_frame}")

    small_first = _resize(first, scale)
    tracker.init(small_first, _scale_box(init_box, scale))
    last_box_original = init_box
    previous_frame = None

    trajectory = []
    for idx in range(start_frame, end_frame + 1):
        if (idx - start_frame) % every_n != 0:
            continue
        frame = video.read_frame(idx)
        if frame is None:
            break
        small = _resize(frame, scale)
        ok, box = tracker.update(small)
        if not ok:
            # Do not invent a position or silently drift onto a player. A
            # single center click is enough to make a same-size new ROI.
            box = _select_reacquisition_box(frame, idx, last_box_original)
            if box is None:
                break
            tracker = _make_tracker()
            tracker.init(small, _scale_box(box, scale))
            last_box_original = box
            previous_frame = frame
            continue
        cx = (box[0] + box[2] / 2) / scale   # back to original pixels
        cy = (box[1] + box[3] / 2) / scale
        last_box_original = _unscale_box(box, scale)
        if _is_player_sized_white_target(frame, (cx, cy)):
            candidate = _find_small_moving_white_ball(
                previous_frame,
                frame,
                expected_center=(cx, cy),
                search_radius=max(60, 4 * max(last_box_original[2:])),
            )
            if candidate is not None:
                print(f"White-shirt guard re-acquired small moving ball at frame {idx}.")
                box = _box_centered_at(candidate, last_box_original, frame.shape)
                tracker = _make_tracker()
                tracker.init(small, _scale_box(box, scale))
                last_box_original = box
                previous_frame = frame
                continue
            print("Tracker target looks player-sized, not ball-sized.")
            box = _select_reacquisition_box(frame, idx, last_box_original)
            if box is None:
                break
            tracker = _make_tracker()
            tracker.init(small, _scale_box(box, scale))
            last_box_original = box
            previous_frame = frame
            continue
        homography = _homography_for(calibration, frame, video.frame_to_time(idx))
        field = homography.pixel_to_field(cx, cy)
        if not homography.is_on_field(field, tolerance=0.0):
            previous_frame = frame
            continue
        u, v = field
        trajectory.append({
            "time": round(video.frame_to_time(idx), 3),
            "x": round(u, 4),
            "y": round(v, 4),
            "x_meters": round(u * FIELD_LENGTH_METERS, 2),
            "y_meters": round(v * FIELD_WIDTH_METERS, 2),
            "tracking_status": "tracked",
            "source": "manual_tracker",
        })
        previous_frame = frame

    return trajectory


def _resize(frame, scale):
    if scale == 1.0:
        return frame
    return cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def _homography_for(calibration, frame, timestamp):
    """Use frame-aware adjustment when available; support saved timelines too."""
    if hasattr(calibration, "homography_for"):
        return calibration.homography_for(frame, timestamp)
    return calibration.homography_at(timestamp)


def _scale_box(box, scale):
    x, y, w, h = box
    # OpenCV trackers expect an integer bounding box.
    return (int(x * scale), int(y * scale), int(w * scale), int(h * scale))


def _unscale_box(box, scale):
    x, y, w, h = box
    return (x / scale, y / scale, w / scale, h / scale)


def _select_reacquisition_box(frame, frame_index, previous_box):
    """Ask for one ball-center click after the appearance tracker loses it."""
    print(f"Tracker lost the ball at frame {frame_index}.")
    window = "Tracker lost ball - click center, ENTER to continue"
    selected = {"center": None}

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            selected["center"] = (x, y)

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)
    try:
        while True:
            display = frame.copy()
            text = "Tracker lost ball: click its center, ENTER=continue, q=stop"
            cv2.putText(display, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(display, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 0, 0), 1, cv2.LINE_AA)
            if selected["center"]:
                preview = _box_centered_at(selected["center"], previous_box, frame.shape)
                x, y, w, h = map(int, preview)
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 255), 2)
            cv2.imshow(window, display)
            key = cv2.waitKey(20) & 0xFF
            if key in (ord("q"), 27):
                return None
            if key in (13, 10) and selected["center"]:
                return _box_centered_at(selected["center"], previous_box, frame.shape)
    finally:
        cv2.destroyWindow(window)


def _box_centered_at(center, previous_box, frame_shape):
    """Reuse the last ROI dimensions while keeping the new ROI on-screen."""
    center_x, center_y = center
    _, _, width, height = previous_box
    width = max(2, min(width, frame_shape[1]))
    height = max(2, min(height, frame_shape[0]))
    left = min(max(center_x - width / 2, 0), frame_shape[1] - width)
    top = min(max(center_y - height / 2, 0), frame_shape[0] - height)
    return left, top, width, height


def _white_mask(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return cv2.inRange(
        hsv,
        (0, 0, WHITE_PIXEL_MIN_VALUE),
        (180, WHITE_PIXEL_MAX_SATURATION, 255),
    )


def _scaled_white_limits(frame):
    scale = frame.shape[0] * frame.shape[1] / (1280 * 720)
    return (
        max(1, round(BALL_WHITE_MIN_PIXELS * scale)),
        max(12, round(BALL_WHITE_MAX_PIXELS * scale)),
        max(8, round(PLAYER_WHITE_COMPONENT_MIN_PIXELS * scale)),
    )


def _is_player_sized_white_target(frame, center):
    """Return True only when the track center falls on a large white region."""
    mask = _white_mask(frame)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    x = min(max(round(center[0]), 0), frame.shape[1] - 1)
    y = min(max(round(center[1]), 0), frame.shape[0] - 1)
    label = labels[y, x]
    if label == 0 or label >= count:
        return False
    _, _, player_min = _scaled_white_limits(frame)
    return stats[label, cv2.CC_STAT_AREA] >= player_min


def _find_small_moving_white_ball(previous_frame, frame, expected_center,
                                  search_radius):
    """Find a ball-sized moving white component near a suspicious tracker hit."""
    if previous_frame is None:
        return None
    current_white = _white_mask(frame)
    previous_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    motion = cv2.absdiff(previous_gray, current_gray)
    motion = cv2.threshold(motion, 25, 255, cv2.THRESH_BINARY)[1]
    motion = cv2.dilate(motion, np.ones((3, 3), np.uint8), iterations=1)
    _, _, stats, centroids = cv2.connectedComponentsWithStats(current_white)
    ball_min, ball_max, _ = _scaled_white_limits(frame)
    candidates = []
    for label in range(1, len(stats)):
        x, y, width, height, area = stats[label]
        if not ball_min <= area <= ball_max:
            continue
        moved = cv2.countNonZero(motion[y:y + height, x:x + width])
        if moved == 0:
            continue
        center = tuple(centroids[label])
        distance = np.linalg.norm(np.asarray(center) - expected_center)
        if distance <= search_radius:
            candidates.append((distance, center))
    return min(candidates, default=(None, None), key=lambda item: item[0])[1]
