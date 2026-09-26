"""
PrerecordedSource: serves ball positions from a saved timestamped trajectory.

Trajectory file format (normalized field coordinates):
    [
      {"time": 0.00, "x": 0.22, "y": 0.61},
      {"time": 0.10, "x": 0.24, "y": 0.60},
      ...
    ]

Positions are interpolated linearly between samples, so playback is driven by
timestamps rather than frame counts and stays smooth regardless of frame rate.
"""

import json
import os

from tracking.position_source import PositionSource
from config import TRAJECTORY_DIR


class PrerecordedSource(PositionSource):
    def __init__(self, points):
        # points: list of dicts with time/x/y, kept sorted by time.
        self.points = sorted(points, key=lambda p: p["time"])
        if not self.points:
            raise ValueError("trajectory is empty")

    # -- construction ------------------------------------------------------
    @classmethod
    def from_file(cls, path):
        with open(path) as f:
            return cls(json.load(f))

    @classmethod
    def from_name(cls, name):
        return cls.from_file(trajectory_path(name))

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.points, f, indent=2)

    # -- lookup ------------------------------------------------------------
    def get_position(self, timestamp):
        pts = self.points
        # Clamp to the ends of the known trajectory.
        if timestamp <= pts[0]["time"]:
            return pts[0]["x"], pts[0]["y"]
        if timestamp >= pts[-1]["time"]:
            return pts[-1]["x"], pts[-1]["y"]

        # Binary-free linear scan is fine: trajectories are small. Find the
        # bracketing pair and interpolate.
        lo = pts[0]
        for hi in pts[1:]:
            if timestamp <= hi["time"]:
                span = hi["time"] - lo["time"]
                frac = 0.0 if span == 0 else (timestamp - lo["time"]) / span
                x = lo["x"] + (hi["x"] - lo["x"]) * frac
                y = lo["y"] + (hi["y"] - lo["y"]) * frac
                return x, y
            lo = hi
        return pts[-1]["x"], pts[-1]["y"]

    def duration(self):
        return self.points[-1]["time"]


def trajectory_path(name):
    return os.path.join(TRAJECTORY_DIR, f"{name}.json")
