"""Small camera-motion compensation for an otherwise fixed field view."""

import cv2
import numpy as np

from calibration.homography import FieldHomography


class AdaptiveCalibration:
    """Update each saved view from its original landmark positions.

    Lucas-Kanade optical flow follows the manually clicked field landmarks
    (normally white-line intersections) from the segment's reference frame to
    the current frame. Rebuilding the homography from those moved landmarks
    keeps the projected grid aligned during a slight pan, shake, or zoom.

    It is deliberately conservative: if fewer than four landmarks can be
    followed forward and backward consistently, it returns the saved mapping.
    """

    def __init__(self, video, calibration):
        self.calibration = calibration
        self.references = []
        for segment in calibration.segments:
            frame_index = video.time_to_frame(segment["start_time"])
            frame = video.read_frame(frame_index)
            homography = segment["homography"]
            points = homography.image_points or []
            if frame is None or len(points) < 4 or not homography.field_points:
                reference = None
            else:
                reference = {
                    "gray": cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                    "points": np.asarray(points, dtype=np.float32).reshape(-1, 1, 2),
                    "field_points": homography.field_points,
                    "static": homography,
                }
            self.references.append(reference)
        self.last_inlier_count = 0

    def homography_at(self, timestamp):
        """Preserve the static-calibration interface for non-frame callers."""
        return self.calibration.homography_at(timestamp)

    def homography_for(self, frame, timestamp):
        segment_index = self._segment_index(timestamp)
        reference = self.references[segment_index]
        static = self.calibration.segments[segment_index]["homography"]
        if reference is None or frame is None:
            self.last_inlier_count = 0
            return static

        current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tracked, forward_status, _ = cv2.calcOpticalFlowPyrLK(
            reference["gray"], current_gray, reference["points"], None,
            winSize=(21, 21), maxLevel=3,
        )
        if tracked is None or forward_status is None:
            self.last_inlier_count = 0
            return static
        returned, backward_status, _ = cv2.calcOpticalFlowPyrLK(
            current_gray, reference["gray"], tracked, None,
            winSize=(21, 21), maxLevel=3,
        )
        if returned is None or backward_status is None:
            self.last_inlier_count = 0
            return static

        round_trip_error = np.linalg.norm(
            returned.reshape(-1, 2) - reference["points"].reshape(-1, 2), axis=1
        )
        valid = (
            forward_status.reshape(-1).astype(bool)
            & backward_status.reshape(-1).astype(bool)
            & (round_trip_error < 2.0)
        )
        self.last_inlier_count = int(valid.sum())
        if self.last_inlier_count < 4:
            return static
        try:
            return FieldHomography.from_correspondences(
                tracked.reshape(-1, 2)[valid],
                np.asarray(reference["field_points"])[valid],
            )
        except ValueError:
            return static

    def _segment_index(self, timestamp):
        index = 0
        for candidate, segment in enumerate(self.calibration.segments[1:], start=1):
            if timestamp < segment["start_time"]:
                break
            index = candidate
        return index
