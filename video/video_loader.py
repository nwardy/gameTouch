"""
Thin wrapper around cv2.VideoCapture.

Exposes frame rate, resolution, and timestamp <-> frame helpers. Keeps random
access (read_frame) available for the offline tracking pass, and sequential
reads for playback. No large buffers are held.
"""

import cv2


class VideoLoader:
    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise FileNotFoundError(f"could not open video: {path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._pos = 0  # next sequential frame index

    # -- timing helpers ----------------------------------------------------
    def frame_to_time(self, index):
        return index / self.fps

    def time_to_frame(self, seconds):
        return int(round(seconds * self.fps))

    def duration(self):
        return self.frame_count / self.fps if self.fps else 0.0

    # -- reading -----------------------------------------------------------
    def read_frame(self, index):
        """Random-access read of a specific frame index (returns BGR or None)."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.cap.read()
        self._pos = index + 1
        return frame if ok else None

    def read_next(self):
        """Sequential read; returns (index, frame) or (None, None) at end."""
        ok, frame = self.cap.read()
        if not ok:
            return None, None
        idx = self._pos
        self._pos += 1
        return idx, frame

    def first_frame(self):
        return self.read_frame(0)

    def release(self):
        if self.cap is not None:
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
