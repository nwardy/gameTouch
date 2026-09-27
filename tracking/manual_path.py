"""Timestamped manual ball-path annotation for clips too hard to auto-track."""

import cv2

from config import FIELD_LENGTH_METERS, FIELD_WIDTH_METERS
from tracking.goal_detection import is_goal_position, nearest_goal_net_position


def annotate_manual_path(video, calibration, initial_points=None, sport="soccer"):
    """Let the user click the ball over time and return a saved-path payload.

    The annotation is deliberately point-based rather than a freehand line:
    every click is tied to the displayed video frame, which keeps the resulting
    bird's-eye movement synchronized with playback.
    """
    window = "Manual ball path"
    current_index = 0
    playing = False
    # Resuming preserves prior work while letting a user correct only a missed
    # scoring frame or add the final goal event.
    points = [dict(point) for point in (initial_points or [])]
    goal_click_armed = {"value": False}
    point_side_armed = {"value": None}

    def record_click(event, px, py, _flags, _param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        timestamp = video.frame_to_time(current_index)
        homography = _homography_for(calibration, frame, timestamp)
        field = homography.pixel_to_field(px, py)
        is_goal = goal_click_armed["value"] or is_goal_position(field)
        if not homography.is_on_field(field, tolerance=0.0) and not is_goal:
            print("That click is outside the pitch and goal nets; no point saved.")
            return
        if goal_click_armed["value"]:
            field = nearest_goal_net_position(field)
            goal_click_armed["value"] = False
        u, v = field
        point = {
            "time": round(timestamp, 3),
            "x": round(u, 4),
            "y": round(v, 4),
            "x_meters": round(u * homography.field_length_meters, 2),
            "y_meters": round(v * homography.field_width_meters, 2),
            "tracking_status": "manual",
            "source": "manual_path",
        }
        if is_goal:
            point["event"] = "goal"
        if point_side_armed["value"]:
            point["event"] = "tennis_point"
            point["side"] = point_side_armed["value"]
            point_side_armed["value"] = None
        points[:] = [item for item in points if item["time"] != point["time"]]
        points.append(point)
        label = " GOAL" if is_goal else ""
        print(f"Saved ball point at t={point['time']:.2f}s{label}")

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, record_click)
    try:
        while True:
            frame = video.read_frame(current_index)
            if frame is None:
                break
            display = _draw_annotation_overlay(
                frame, current_index, video, points, playing,
                goal_click_armed["value"],
            )
            cv2.imshow(window, display)

            delay = max(1, round(1000 / video.fps)) if playing else 0
            key = cv2.waitKey(delay) & 0xFF
            if key in (13, 10):  # ENTER
                break
            if key in (ord("q"), 27):
                return None
            if key in (8, 127):  # backspace/delete
                _remove_current_or_latest_point(points, video.frame_to_time(current_index))
            elif key == ord(" "):
                playing = not playing
            elif key in (ord("."), ord("d")):
                playing = False
                current_index = min(current_index + 1, video.frame_count - 1)
            elif key in (ord(","), ord("a")):
                playing = False
                current_index = max(current_index - 1, 0)
            elif key == ord("l"):
                playing = False
                current_index = min(current_index + 5, video.frame_count - 1)
            elif key == ord("j"):
                playing = False
                current_index = max(current_index - 5, 0)
            elif key == ord("g"):
                goal_click_armed["value"] = True
                print("Goal click armed: click the ball in the net. Annotation continues.")
            elif sport.startswith("tennis") and key in (ord("1"), ord("2")):
                point_side_armed["value"] = "near" if key == ord("1") else "far"
                print(f"Tennis point armed for {point_side_armed['value']} side; click ball.")
            elif playing:
                current_index = min(current_index + 1, video.frame_count - 1)
                if current_index == video.frame_count - 1:
                    playing = False
    finally:
        cv2.destroyWindow(window)

    return sorted(points, key=lambda point: point["time"])


def _homography_for(calibration, frame, timestamp):
    """Use frame-aware adjustment when available; support saved timelines too."""
    if hasattr(calibration, "homography_for"):
        return calibration.homography_for(frame, timestamp)
    return calibration.homography_at(timestamp)


def _remove_current_or_latest_point(points, timestamp):
    for index, point in enumerate(points):
        if point["time"] == round(timestamp, 3):
            points.pop(index)
            return
    if points:
        points.pop()


def _draw_annotation_overlay(frame, index, video, points, playing, goal_click_armed):
    display = frame.copy()
    state = "PLAYING" if playing else "PAUSED"
    text = (
        f"{state}  t={video.frame_to_time(index):.2f}s  "
        "click=ball  g=goal click  SPACE=play/pause  ./,=frame  l/j=5 frames  "
        "BACKSPACE=undo  ENTER=save"
    )
    cv2.putText(display, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(display, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(display, f"manual points: {len(points)}", (12, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
    if goal_click_armed:
        cv2.putText(display, "GOAL CLICK ARMED — click ball in net", (12, 74),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 2,
                    cv2.LINE_AA)
    return display
