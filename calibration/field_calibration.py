"""
Interactive calibration from visible soccer markings. Each clicked image point
is paired with a real (x, y) pitch position in metres, so a broadcast view does
not need to show the four outer corners.
"""

import os

import cv2

from calibration.homography import FieldHomography
from calibration.calibration_timeline import CalibrationTimeline
from config import CALIBRATION_DIR, FIELD_LENGTH_METERS, FIELD_WIDTH_METERS


def calibration_path(name):
    return os.path.join(CALIBRATION_DIR, f"{name}.json")


def load_calibration(name):
    path = calibration_path(name)
    if os.path.exists(path):
        return CalibrationTimeline.load(path)
    return None


def save_calibration(calibration, name):
    path = calibration_path(name)
    calibration.save(path)
    print(f"Saved calibration -> {path}")


def calibrate_from_frame(frame):
    """Pair visible image landmarks with field yards and save their homography.

    Controls: click a landmark, then enter its ``x,y`` yard coordinate in the
    terminal. Add at least four well-spread points; ``u`` removes the latest
    pair; ENTER saves; q/ESC aborts. Coordinate convention: x=0 is one goal
    line and x=105 the other; y=0 is the near touchline and y=68 the far.
    """
    image_points = []
    field_points = []
    window = "Field Calibration - click landmark, enter x,y in terminal"

    def on_mouse(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        yard_point = _prompt_for_field_point(x, y)
        if yard_point is not None:
            image_points.append((x, y))
            field_points.append(yard_point)

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)

    while True:
        disp = frame.copy()
        for i, (cx, cy) in enumerate(image_points):
            cv2.circle(disp, (cx, cy), 6, (0, 255, 0), -1)
            fx, fy = field_points[i]
            cv2.putText(disp, f"{fx:g},{fy:g}", (cx + 8, cy - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        prompt = "Click known landmark; enter x,y in terminal"
        if len(image_points) >= 4:
            prompt = "Click more landmarks or ENTER=confirm  u=undo  q=abort"
        cv2.putText(disp, prompt, (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow(window, disp)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):          # q / ESC
            cv2.destroyWindow(window)
            return None
        if key == ord("u") and image_points:
            image_points.pop()
            field_points.pop()
        if key in (13, 10) and len(image_points) >= 4:  # ENTER
            break

    cv2.destroyWindow(window)
    homography = FieldHomography.from_correspondences(image_points, field_points)
    errors = homography.calibration_error_meters()
    print(f"Calibration landmarks: {len(image_points)}; "
          f"mean reprojection error: {sum(errors) / len(errors):.2f} m")
    return homography


def choose_shift_frame(video):
    """Let the user mark the first stable frame after a camera reposition."""
    window = "Mark camera shift"
    index = 0
    playing = False
    cv2.namedWindow(window)
    try:
        while True:
            frame = video.read_frame(index)
            if frame is None:
                return None
            display = frame.copy()
            state = "PLAYING" if playing else "PAUSED"
            text = (
                f"{state}  t={video.frame_to_time(index):.2f}s  "
                "mark the first stable post-shift frame: SPACE=play/pause  "
                "./,=frame  l/j=5 frames  ENTER=mark  q=abort"
            )
            cv2.putText(display, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(display, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.imshow(window, display)
            delay = max(1, round(1000 / video.fps)) if playing else 0
            key = cv2.waitKey(delay) & 0xFF
            if key in (13, 10):
                return index
            if key in (ord("q"), 27):
                return None
            if key == ord(" "):
                playing = not playing
            elif key in (ord("."), ord("d")):
                playing = False
                index = min(index + 1, video.frame_count - 1)
            elif key in (ord(","), ord("a")):
                playing = False
                index = max(index - 1, 0)
            elif key == ord("l"):
                playing = False
                index = min(index + 5, video.frame_count - 1)
            elif key == ord("j"):
                playing = False
                index = max(index - 5, 0)
            elif playing:
                index = min(index + 1, video.frame_count - 1)
                if index == video.frame_count - 1:
                    playing = False
    finally:
        cv2.destroyWindow(window)


def _prompt_for_field_point(px, py):
    """Read the field coordinate for the just-clicked image landmark."""
    while True:
        value = input(
            f"Clicked pixel ({px}, {py}). Enter pitch x,y metres "
            f"(x=0..{FIELD_LENGTH_METERS:g}, y=0..{FIELD_WIDTH_METERS:g}) "
            "or blank to discard: "
        ).strip()
        if not value:
            return None
        try:
            x_text, y_text = value.split(",")
            field_x, field_y = float(x_text), float(y_text)
        except ValueError:
            print("Use two numbers separated by a comma, for example: 52.5,34")
            continue
        if not 0 <= field_x <= FIELD_LENGTH_METERS:
            print("Pitch x must be between 0 and 105.")
            continue
        if not 0 <= field_y <= FIELD_WIDTH_METERS:
            print("Pitch y must be between 0 and 68.")
            continue
        return field_x, field_y
