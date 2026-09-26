"""
Field homography: map image pixels -> normalized field coordinates (0..1).

The four calibrated field corners are supplied in this order:
    corner 1: top-left      -> field (0, 0)
    corner 2: top-right     -> field (1, 0)
    corner 3: bottom-right  -> field (1, 1)
    corner 4: bottom-left   -> field (0, 1)

Keeping the destination as the unit square means pixel_to_field already returns
the normalized coordinate the rest of the program expects.
"""

import json
import os

import numpy as np
import cv2

# Destination = unit square, matching the corner order above.
_DST = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)


class FieldHomography:
    def __init__(self, matrix, corners=None):
        self.matrix = np.asarray(matrix, dtype=np.float64)
        self.corners = corners  # original pixel corners, for redraw/debug

    @classmethod
    def from_corners(cls, corners):
        """corners: list of 4 (x, y) pixel points in TL, TR, BR, BL order."""
        src = np.array(corners, dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(src, _DST)
        return cls(matrix, corners=[list(map(float, c)) for c in corners])

    def pixel_to_field(self, px, py):
        """Map a pixel (px, py) to normalized field (u, v)."""
        pt = np.array([px, py, 1.0], dtype=np.float64)
        u, v, w = self.matrix @ pt
        if w == 0:
            return None
        return float(u / w), float(v / w)

    # -- persistence -------------------------------------------------------
    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(
                {"matrix": self.matrix.tolist(), "corners": self.corners},
                f,
                indent=2,
            )

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        return cls(data["matrix"], corners=data.get("corners"))
