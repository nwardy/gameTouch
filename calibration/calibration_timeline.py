"""Choose the correct fixed-camera calibration for each part of a video."""

import json
import os

from calibration.homography import FieldHomography


class CalibrationTimeline:
    """An ordered set of calibrations separated by deliberate camera shifts.

    This intentionally handles cuts or settled repositioning, not continuous
    pan/zoom.  The latest segment whose start time has passed is active.
    """

    def __init__(self, segments):
        if not segments:
            raise ValueError("at least one calibration segment is required")
        self.segments = sorted(segments, key=lambda segment: segment["start_time"])
        if self.segments[0]["start_time"] != 0.0:
            raise ValueError("the first calibration segment must start at 0 seconds")

    @classmethod
    def single(cls, homography):
        return cls([{"start_time": 0.0, "homography": homography}])

    def homography_at(self, timestamp):
        active = self.segments[0]["homography"]
        for segment in self.segments[1:]:
            if timestamp < segment["start_time"]:
                break
            active = segment["homography"]
        return active

    def add_shift(self, start_time, homography):
        """Replace or append the calibration beginning at ``start_time``."""
        start_time = round(float(start_time), 3)
        if start_time <= 0:
            raise ValueError("a camera-shift calibration must start after 0 seconds")
        self.segments = [
            segment for segment in self.segments
            if segment["start_time"] != start_time
        ]
        self.segments.append({"start_time": start_time, "homography": homography})
        self.segments.sort(key=lambda segment: segment["start_time"])

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "format": "calibration_timeline_v1",
            "segments": [
                {
                    "start_time": segment["start_time"],
                    "homography": segment["homography"].to_dict(),
                }
                for segment in self.segments
            ],
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        # Existing one-view calibration files remain valid without migration.
        if "segments" not in data:
            return cls.single(FieldHomography.from_dict(data))
        return cls([
            {
                "start_time": float(segment["start_time"]),
                "homography": FieldHomography.from_dict(segment["homography"]),
            }
            for segment in data["segments"]
        ])
