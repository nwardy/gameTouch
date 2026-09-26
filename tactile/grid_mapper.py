"""
Grid mapping: normalized field coordinates  <->  4x5 tactile cell.

Coordinate convention (normalized, 0..1):
    x = 0.0 left edge      x = 1.0 right edge
    y = 0.0 top sideline   y = 1.0 bottom sideline

Human-facing cells are 1-based:
    row    in 1..GRID_ROWS   (follows y)
    column in 1..GRID_COLS   (follows x)
"""

from config import GRID_ROWS, GRID_COLS, DEBOUNCE_FRAMES, HYSTERESIS


def field_to_cell(x, y, rows=GRID_ROWS, cols=GRID_COLS):
    """Map normalized (x, y) to a 1-based (row, column).

    Values are clamped to the field, so out-of-range inputs still land on an
    edge cell rather than an invalid one.
    """
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    column = min(int(x * cols), cols - 1) + 1   # 1..cols
    row = min(int(y * rows), rows - 1) + 1       # 1..rows
    return row, column


def cell_to_center(row, column, rows=GRID_ROWS, cols=GRID_COLS):
    """Return the normalized (x, y) center of a 1-based (row, column).

    Useful for the top-down visualization and debugging.
    """
    x = (column - 0.5) / cols
    y = (row - 0.5) / rows
    return x, y


class CellDebouncer:
    """Prevents the tactile output from chattering between neighboring cells.

    Two mechanisms, both cheap:
      * Hysteresis: the ball must move a small margin *past* a cell boundary
        (not merely touch it) before a change is considered.
      * Debounce:   a candidate new cell must persist for DEBOUNCE_FRAMES
        consecutive samples before it becomes the active cell.

    This matters because we drive mechanical relays and do not want to cycle
    them when the ball is loitering near a boundary.
    """

    def __init__(self, debounce_frames=DEBOUNCE_FRAMES, hysteresis=HYSTERESIS,
                 rows=GRID_ROWS, cols=GRID_COLS):
        self.debounce_frames = debounce_frames
        self.hysteresis = hysteresis
        self.rows = rows
        self.cols = cols
        self.current_cell = None       # committed (row, column)
        self._candidate = None
        self._candidate_count = 0

    def update(self, x, y):
        """Feed a smoothed normalized position, get the committed cell back.

        Returns the (row, column) that should currently be active.
        """
        raw_cell = field_to_cell(x, y, self.rows, self.cols)

        # First ever sample: accept immediately.
        if self.current_cell is None:
            self.current_cell = raw_cell
            self._candidate = raw_cell
            self._candidate_count = self.debounce_frames
            return self.current_cell

        # Same as committed cell: reset any pending change.
        if raw_cell == self.current_cell:
            self._candidate = self.current_cell
            self._candidate_count = 0
            return self.current_cell

        # A different cell. Only treat it as a real candidate if the ball has
        # moved clearly past the boundary (hysteresis), otherwise stay put.
        if not self._past_boundary(x, y):
            return self.current_cell

        if raw_cell == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = raw_cell
            self._candidate_count = 1

        if self._candidate_count >= self.debounce_frames:
            self.current_cell = self._candidate
            self._candidate_count = 0

        return self.current_cell

    def _past_boundary(self, x, y):
        """True if (x, y) is at least `hysteresis` beyond the current cell."""
        row, col = self.current_cell
        # Current cell's normalized bounds.
        x0, x1 = (col - 1) / self.cols, col / self.cols
        y0, y1 = (row - 1) / self.rows, row / self.rows
        m = self.hysteresis
        return (x < x0 - m or x > x1 + m or y < y0 - m or y > y1 + m)
