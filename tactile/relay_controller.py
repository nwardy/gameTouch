"""
Jetson relay controller.

Drives 9 relay channels (4 rows + 5 columns) over the 40-pin header using
BOARD numbering. All HIGH/LOW polarity lives behind relay_on/relay_off so the
rest of the code never assumes a level.

This module imports Jetson.GPIO lazily inside setup() so it can be *imported*
on a MacBook without the library present. Only call setup() on real hardware.
"""

import time

from tactile.relay_config import (
    ROW_PINS,
    COLUMN_PINS,
    ALL_RELAY_PINS,
    RELAY_ACTIVE_LOW,
    RELAY_SWITCH_DELAY,
)
from config import GRID_ROWS, GRID_COLS

GPIO = None  # populated in setup()


class RelayController:
    def __init__(self, switch_delay=RELAY_SWITCH_DELAY, active_low=RELAY_ACTIVE_LOW):
        self.switch_delay = switch_delay
        self.active_low = active_low
        self.current_cell = None
        self._active_pins = set()
        self._is_setup = False

    # -- lifecycle ---------------------------------------------------------
    def setup(self):
        """Import Jetson.GPIO, configure pins as outputs, everything OFF."""
        global GPIO
        if GPIO is None:
            import Jetson.GPIO as _GPIO  # noqa: N814  (lazy hardware-only import)
            GPIO = _GPIO
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        # Initialize every pin to the OFF level to avoid a glitch pulse.
        off_level = self._level(False)
        for pin in ALL_RELAY_PINS:
            GPIO.setup(pin, GPIO.OUT, initial=off_level)
        self._active_pins = set()
        self.current_cell = None
        self._is_setup = True

    def cleanup(self):
        """Turn everything off and release the GPIO lines. Safe to call twice."""
        try:
            self.all_off()
        finally:
            if GPIO is not None and self._is_setup:
                GPIO.cleanup()
            self._is_setup = False

    # -- polarity ----------------------------------------------------------
    def _level(self, on):
        """Translate a logical on/off into the physical HIGH/LOW for this board."""
        if self.active_low:
            return GPIO.LOW if on else GPIO.HIGH
        return GPIO.HIGH if on else GPIO.LOW

    def relay_on(self, pin):
        GPIO.output(pin, self._level(True))
        self._active_pins.add(pin)

    def relay_off(self, pin):
        GPIO.output(pin, self._level(False))
        self._active_pins.discard(pin)

    def all_off(self):
        if GPIO is None or not self._is_setup:
            return
        for pin in ALL_RELAY_PINS:
            GPIO.output(pin, self._level(False))
        self._active_pins = set()
        self.current_cell = None

    # -- high level --------------------------------------------------------
    def select_cell(self, row, column):
        """Activate the relay pair for a 1-based (row, column).

        Does nothing if the cell is unchanged (avoids needless relay wear).
        Invalid coordinates never touch the hardware.
        """
        if not (1 <= row <= GRID_ROWS and 1 <= column <= GRID_COLS):
            raise ValueError(
                f"cell out of range: row={row} (1..{GRID_ROWS}), "
                f"column={column} (1..{GRID_COLS})"
            )

        if (row, column) == self.current_cell:
            return  # already active; do not cycle the relays

        row_pin = ROW_PINS[row - 1]
        col_pin = COLUMN_PINS[column - 1]

        # 1. turn off previously selected relays
        self.all_off()
        # 2. short settle before energizing the new pair
        if self.switch_delay:
            time.sleep(self.switch_delay)
        # 3. activate row, 4. activate column
        self.relay_on(row_pin)
        self.relay_on(col_pin)

        self.current_cell = (row, column)
