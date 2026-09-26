"""
Ball tracking / trajectory generation for prerecorded clips.

Design priorities (per project spec): be fast and simple, and lean on
semi-manual initialization rather than heavy inference. We only need to know
which of 20 large field regions the ball is in, so a lightweight OpenCV tracker
seeded by one manual click/box is plenty for V1.

Output is always a normalized-field trajectory (list of {time, x, y}), which is
then saved and served by PrerecordedSource. The tracker never talks to the
tactile system directly, keeping vision and output loosely coupled.
"""

import cv2

from config import PROCESS_WIDTH, PROCESS_EVERY_N_FRAMES


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


def track_clip(video, homography, init_box, start_frame=0, end_frame=None,
               every_n=PROCESS_EVERY_N_FRAMES, process_width=PROCESS_WIDTH):
    """Track the ball across a frame range and return a normalized trajectory.

    Parameters
    ----------
    video        : VideoLoader (already opened)
    homography   : FieldHomography mapping pixels -> normalized field
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
            # Lost the ball; stop rather than emit garbage. The play interval
            # can be re-clicked, or automation improved later.
            break
        cx = (box[0] + box[2] / 2) / scale   # back to original pixels
        cy = (box[1] + box[3] / 2) / scale
        field = homography.pixel_to_field(cx, cy)
        if field is None:
            continue
        u, v = field
        trajectory.append({
            "time": round(video.frame_to_time(idx), 3),
            "x": round(min(max(u, 0.0), 1.0), 4),
            "y": round(min(max(v, 0.0), 1.0), 4),
        })

    return trajectory


def _resize(frame, scale):
    if scale == 1.0:
        return frame
    return cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def _scale_box(box, scale):
    x, y, w, h = box
    # OpenCV trackers expect an integer bounding box.
    return (int(x * scale), int(y * scale), int(w * scale), int(h * scale))
