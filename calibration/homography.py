"""
Field homography: map image pixels -> normalized field coordinates (0..1).

Calibration accepts four or more visible ground landmarks. Each image point is
paired with its known soccer-pitch position in metres, so a broadcast view need
not show the four outer corners. The saved mapping still returns normalized
coordinates because the tactile system depends on that interface.
"""

import json
import os

import numpy as np
import cv2

from config import FIELD_LENGTH_METERS, FIELD_WIDTH_METERS


class FieldHomography:
    def __init__(self, matrix, corners=None, image_points=None, field_points=None,
                 sport="soccer", field_length_meters=FIELD_LENGTH_METERS,
                 field_width_meters=FIELD_WIDTH_METERS):
        self.matrix = np.asarray(matrix, dtype=np.float64)
        # ``corners`` is retained for old calibration files and the debug
        # outline.  New calibrations use arbitrary visible landmarks instead.
        self.corners = corners
        self.image_points = image_points or corners
        self.field_points = field_points
        self.sport = sport
        self.field_length_meters = field_length_meters
        self.field_width_meters = field_width_meters

    @classmethod
    def from_corners(cls, corners):
        """Create a legacy full-field-corner calibration."""
        src = np.array(corners, dtype=np.float32)
        dst = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(src, dst)
        points = [list(map(float, c)) for c in corners]
        return cls(matrix, corners=points, image_points=points,
                   field_points=[
                       [0.0, 0.0],
                       [FIELD_LENGTH_METERS, 0.0],
                       [FIELD_LENGTH_METERS, FIELD_WIDTH_METERS],
                       [0.0, FIELD_WIDTH_METERS],
                   ])

    @classmethod
    def from_correspondences(cls, image_points, field_points_meters,
                             sport="soccer", field_length_meters=FIELD_LENGTH_METERS,
                             field_width_meters=FIELD_WIDTH_METERS):
        """Build a field map from >=4 visible pixel-to-yard correspondences.

        ``field_points_meters`` uses x=0..105 from one goal line to the other
        and y=0..68 from the near touchline to the far touchline. RANSAC
        lets an extra accidental click be ignored instead of distorting the
        complete field map.
        """
        if len(image_points) != len(field_points_meters):
            raise ValueError("image and field point counts must match")
        if len(image_points) < 4:
            raise ValueError("at least four field landmarks are required")

        src = np.asarray(image_points, dtype=np.float32)
        meters = np.asarray(field_points_meters, dtype=np.float32)
        if np.any(meters[:, 0] < 0) or np.any(meters[:, 0] > field_length_meters):
            raise ValueError("field x coordinate is outside this sport's court")
        if np.any(meters[:, 1] < 0) or np.any(meters[:, 1] > field_width_meters):
            raise ValueError("field y coordinate is outside this sport's court")

        dst = meters.copy()
        dst[:, 0] /= field_length_meters
        dst[:, 1] /= field_width_meters
        matrix, _inliers = cv2.findHomography(src, dst, cv2.RANSAC, 0.02)
        if matrix is None:
            raise ValueError("could not calculate a field homography")

        return cls(
            matrix,
            image_points=[list(map(float, point)) for point in image_points],
            field_points=[list(map(float, point)) for point in field_points_meters],
            sport=sport,
            field_length_meters=field_length_meters,
            field_width_meters=field_width_meters,
        )

    def pixel_to_field(self, px, py):
        """Map a pixel (px, py) to normalized field (u, v)."""
        pt = np.array([px, py, 1.0], dtype=np.float64)
        u, v, w = self.matrix @ pt
        if w == 0:
            return None
        return float(u / w), float(v / w)

    def pixel_to_meters(self, px, py):
        """Map a pixel to (x, y) pitch metres, or None for an invalid point."""
        field = self.pixel_to_field(px, py)
        if field is None:
            return None
        u, v = field
        return u * self.field_length_meters, v * self.field_width_meters

    @staticmethod
    def is_on_field(field, tolerance=0.03):
        """Return whether a normalized point is plausibly on the field."""
        if field is None:
            return False
        u, v = field
        return -tolerance <= u <= 1 + tolerance and -tolerance <= v <= 1 + tolerance

    def calibration_error_meters(self):
        """Per-landmark mapping error in metres, useful for manual QA."""
        if not self.image_points or not self.field_points:
            return []
        errors = []
        for image_point, expected in zip(self.image_points, self.field_points):
            actual = self.pixel_to_meters(*image_point)
            errors.append(float(np.linalg.norm(np.asarray(actual) - expected)))
        return errors

    # -- persistence -------------------------------------------------------
    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_dict(self):
        """Return a JSON-safe representation for single or segmented saves."""
        return {
            "matrix": self.matrix.tolist(),
            "corners": self.corners,
            "image_points": self.image_points,
            "field_points": self.field_points,
            "sport": self.sport,
            "field_length_meters": self.field_length_meters,
            "field_width_meters": self.field_width_meters,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["matrix"],
            corners=data.get("corners"),
            image_points=data.get("image_points"),
            field_points=data.get("field_points"),
            sport=data.get("sport", "soccer"),
            field_length_meters=data.get("field_length_meters", FIELD_LENGTH_METERS),
            field_width_meters=data.get("field_width_meters", FIELD_WIDTH_METERS),
        )

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)
