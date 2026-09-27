"""
MockTactileOutput: the MacBook development sink.

Prints the active cell (and the physical pins it *would* drive on a Jetson) so
almost all software development can happen with no hardware connected.
"""

from tactile.tactile_output import TactileOutput
from tactile.relay_config import ROW_PINS, COLUMN_PINS
from config import GRID_ROWS, GRID_COLS


class MockTactileOutput(TactileOutput):
    def __init__(self, quiet=False):
        self.quiet = quiet
        self.current_cell = None

    def set_cell(self, row, column):
        if not (1 <= row <= GRID_ROWS and 1 <= column <= GRID_COLS):
            # Mirror the real controller: invalid coords never "activate".
            raise ValueError(f"cell out of range: row={row}, column={column}")

        if (row, column) == self.current_cell:
            return
        self.current_cell = (row, column)

        if not self.quiet:
            row_pin = ROW_PINS[row - 1]
            col_pin = COLUMN_PINS[column - 1]
            print(
                f"ACTIVE CELL: Row {row}, Column {column}   "
                f"(would drive row_pin={row_pin}, col_pin={col_pin})"
            )

    def all_off(self):
        if self.current_cell is not None and not self.quiet:
            print("ACTIVE CELL: (all off)")
        self.current_cell = None

    def all_on(self):
        self.current_cell = "all"
        if not self.quiet:
            print("ACTIVE CELL: (all 20 sensors on)")

    def pulse_side(self, side):
        print(f"TENNIS POINT: {side} side buzz")
