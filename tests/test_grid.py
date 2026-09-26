#!/usr/bin/env python3
"""
Logical 4x5 grid hardware test.

Cycles through every tactile cell (1,1) .. (4,5) using select_cell(), printing
the cell together with the physical row/column pins it energizes. Touch the
tactile board as it runs to confirm software cell -> correct vibration motor.

    sudo python3 tests/test_grid.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tactile.relay_config import ROW_PINS, COLUMN_PINS
from tactile.relay_controller import RelayController
from config import GRID_ROWS, GRID_COLS

CELL_TEST_TIME = 0.75  # seconds each cell stays active


def main():
    controller = RelayController()
    controller.setup()
    try:
        for row in range(1, GRID_ROWS + 1):
            for column in range(1, GRID_COLS + 1):
                controller.select_cell(row, column)
                row_pin = ROW_PINS[row - 1]
                col_pin = COLUMN_PINS[column - 1]
                print(
                    f"Cell: ({row},{column})\n"
                    f"\n    Row {row}"
                    f"\n    Pin {row_pin}"
                    f"\n\n    Column {column}"
                    f"\n    Pin {col_pin}\n"
                )
                time.sleep(CELL_TEST_TIME)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        controller.cleanup()
        print("relays off, GPIO cleaned up")


if __name__ == "__main__":
    main()
