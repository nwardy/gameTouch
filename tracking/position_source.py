"""
PositionSource: the single abstraction the tactile system depends on.

The rest of the program only ever calls get_position(timestamp) and receives a
normalized field coordinate. It does not care whether that coordinate came from
a saved trajectory, a manual path, offline analysis, or (later) live detection.

Swapping prerecorded -> live means providing a different PositionSource; nothing
downstream changes.
"""

from abc import ABC, abstractmethod


class PositionSource(ABC):
    @abstractmethod
    def get_position(self, timestamp):
        """Return normalized (x, y) for `timestamp` (seconds), or None if the
        ball position is unknown at that time (e.g. before/after the play)."""
        ...

    def duration(self):
        """Optional: total seconds this source can report positions for.
        Return None if unbounded/unknown (e.g. live)."""
        return None
