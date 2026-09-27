"""
Hardware abstraction layer for the tactile field.

The rest of the system talks only to a TactileOutput. It never knows or cares
whether the cell is being printed on a MacBook or energizing relays on a Jetson.
"""

from abc import ABC, abstractmethod


class TactileOutput(ABC):
    """Abstract tactile sink. One active cell at a time (row, column), 1-based."""

    @abstractmethod
    def set_cell(self, row, column):
        ...

    @abstractmethod
    def all_off(self):
        ...

    def all_on(self):
        """Optional celebration effect: energize every matrix line."""
        self.all_off()

    def pulse_side(self, side):
        """Pulse the selected court-side strip for a tennis point."""
        self.controller.pulse_side(side)

    def setup(self):
        """Optional hardware init. No-op by default."""

    def cleanup(self):
        """Optional hardware teardown. No-op by default."""


class JetsonRelayTactileOutput(TactileOutput):
    """TactileOutput backed by the physical relay board on a Jetson.

    Thin adapter over RelayController so hardware wiring stays in one place.
    """

    def __init__(self, controller=None):
        # Import here so this module remains importable on macOS.
        if controller is None:
            from tactile.relay_controller import RelayController
            controller = RelayController()
        self.controller = controller

    def setup(self):
        self.controller.setup()

    def set_cell(self, row, column):
        self.controller.select_cell(row, column)

    def all_off(self):
        self.controller.all_off()

    def all_on(self):
        self.controller.all_on()

    def cleanup(self):
        self.controller.cleanup()
