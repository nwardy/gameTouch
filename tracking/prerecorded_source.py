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
from config import (
    MANUAL_PATH_MAX_INTERPOLATION_GAP_SECONDS,
    MAX_INTERPOLATION_GAP_SECONDS,
    TRAJECTORY_DIR,
)


class PrerecordedSource(PositionSource):
    def __init__(self, points, max_interpolation_gap=MAX_INTERPOLATION_GAP_SECONDS):
        # points: list of dicts with time/x/y, kept sorted by time.
        self.points = sorted(points, key=lambda p: p["time"])
        if not self.points:
            raise ValueError("trajectory is empty")
        self.max_interpolation_gap = max_interpolation_gap

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
        # A missing ball must be unknown, not frozen at its first/last known
        # location for the rest of the clip.
        if timestamp < pts[0]["time"] or timestamp > pts[-1]["time"]:
            return None

        # Binary-free linear scan is fine: trajectories are small. Find the
        # bracketing pair and interpolate.
        lo = pts[0]
        for hi in pts[1:]:
            if timestamp <= hi["time"]:
                span = hi["time"] - lo["time"]
                if span > self._interpolation_limit(lo, hi):
                    return None
                frac = 0.0 if span == 0 else (timestamp - lo["time"]) / span
                x = lo["x"] + (hi["x"] - lo["x"]) * frac
                y = lo["y"] + (hi["y"] - lo["y"]) * frac
                return x, y
            lo = hi
        return pts[-1]["x"], pts[-1]["y"]

    def _interpolation_limit(self, lo, hi):
        """Keep uncertain tracker gaps off, but join deliberate manual clicks."""
        if lo.get("source") == "manual_path" and hi.get("source") == "manual_path":
            return max(self.max_interpolation_gap,
                       MANUAL_PATH_MAX_INTERPOLATION_GAP_SECONDS)
        return self.max_interpolation_gap

    def duration(self):
        return self.points[-1]["time"]

    def goal_time(self):
        """Return the first manual goal timestamp, if this trajectory has one."""
        for point in self.points:
            if point.get("event") == "goal":
                return point["time"]
        return None

    def events_between(self, start_time, end_time):
        return [
            point for point in self.points
            if start_time < point["time"] <= end_time and point.get("event") == "tennis_point"
        ]


def trajectory_path(name):
    return os.path.join(TRAJECTORY_DIR, f"{name}.json")
