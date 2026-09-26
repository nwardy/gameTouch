"""
Interactive field calibration.

Show one frame, let the user click the four field corners in order
(top-left, top-right, bottom-right, bottom-left), then build and save a
FieldHomography so it need not be recreated for the same camera view.
"""

import os

import cv2

from calibration.homography import FieldHomography
from config import CALIBRATION_DIR

_CORNER_LABELS = [
    "1: TOP-LEFT",
    "2: TOP-RIGHT",
    "3: BOTTOM-RIGHT",
    "4: BOTTOM-LEFT",
]


def calibration_path(name):
    return os.path.join(CALIBRATION_DIR, f"{name}.json")


def load_calibration(name):
    path = calibration_path(name)
    if os.path.exists(path):
        return FieldHomography.load(path)
    return None


def calibrate_from_frame(frame, name=None):
    """Click 4 corners on `frame`. Returns a FieldHomography (saved if `name`).

    Controls: left-click to place a corner, 'u' to undo, ENTER to confirm
    once all four are placed, 'q'/ESC to abort (returns None).
    """
    corners = []
    window = "Field Calibration - click TL, TR, BR, BL"

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(corners) < 4:
            corners.append((x, y))

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)

    while True:
        disp = frame.copy()
        for i, (cx, cy) in enumerate(corners):
            cv2.circle(disp, (cx, cy), 6, (0, 255, 0), -1)
            cv2.putText(disp, str(i + 1), (cx + 8, cy - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if len(corners) >= 2:
            cv2.polylines(disp, [_as_int_poly(corners)],
                          len(corners) == 4, (0, 200, 255), 2)

        prompt = (
            "Click " + _CORNER_LABELS[len(corners)]
            if len(corners) < 4 else
            "ENTER=confirm  u=undo  q=abort"
        )
        cv2.putText(disp, prompt, (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow(window, disp)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):          # q / ESC
            cv2.destroyWindow(window)
            return None
        if key == ord("u") and corners:    # undo
            corners.pop()
        if key in (13, 10) and len(corners) == 4:  # ENTER
            break

    cv2.destroyWindow(window)
    homography = FieldHomography.from_corners(corners)
    if name:
        homography.save(calibration_path(name))
        print(f"Saved calibration -> {calibration_path(name)}")
    return homography


def _as_int_poly(points):
    import numpy as np
    return np.array(points, dtype=np.int32).reshape(-1, 1, 2)
