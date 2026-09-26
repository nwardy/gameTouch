"""
Synchronized playback.

Drives the simple real-time loop: for the current timestamp, ask the
PositionSource where the ball is, smooth it, map to a tactile cell (with
debounce), push to the TactileOutput, and (optionally) draw a debug overlay.

Video and tactile output stay in sync via timestamps, not frame counts.
"""

import time

import cv2
import numpy as np

from tactile.grid_mapper import CellDebouncer, cell_to_center
from config import (
    GRID_ROWS,
    GRID_COLS,
    EMA_ALPHA,
    DEBUG_VISUAL,
    LOG_ON_CHANGE_ONLY,
)
from tactile.relay_config import ROW_PINS, COLUMN_PINS


class _EMA:
    """Exponential moving average smoother for the normalized position."""

    def __init__(self, alpha=EMA_ALPHA):
        self.alpha = alpha
        self.x = None
        self.y = None

    def update(self, x, y):
        if self.x is None:
            self.x, self.y = x, y
        else:
            a = self.alpha
            self.x = a * x + (1 - a) * self.x
            self.y = a * y + (1 - a) * self.y
        return self.x, self.y


def play(video, position_source, tactile_output, homography=None,
         debug=DEBUG_VISUAL, realtime=True):
    """Play `video` in sync with `position_source`, driving `tactile_output`.

    Returns normally at end of clip. Caller is responsible for tactile cleanup
    (so relays are always turned off even on Ctrl+C).
    """
    smoother = _EMA()
    debouncer = CellDebouncer()
    last_logged_cell = None
    window = "Tactile Field - debug"

    start_wall = time.time()
    while True:
        idx, frame = video.read_next()
        if frame is None:
            break
        timestamp = video.frame_to_time(idx)

        pos = position_source.get_position(timestamp)
        cell = None
        field = None
        if pos is not None:
            sx, sy = smoother.update(*pos)
            field = (sx, sy)
            row, column = debouncer.update(sx, sy)
            cell = (row, column)
            tactile_output.set_cell(row, column)

            if cell != last_logged_cell or not LOG_ON_CHANGE_ONLY:
                _log(timestamp, field, cell)
                last_logged_cell = cell

        if debug:
            disp = _draw_overlay(frame, field, cell, homography, timestamp)
            cv2.imshow(window, disp)
            # pace to real time relative to video fps
            if _wait_and_maybe_quit(video, idx, start_wall, realtime):
                break

    if debug:
        cv2.destroyWindow(window)


# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------
def _log(timestamp, field, cell):
    row, column = cell
    row_pin = ROW_PINS[row - 1]
    col_pin = COLUMN_PINS[column - 1]
    print(
        f"t={timestamp:.3f}  field=({field[0]:.3f}, {field[1]:.3f})  "
        f"cell=({row},{column})  row_pin={row_pin}  col_pin={col_pin}"
    )


# ---------------------------------------------------------------------------
# timing
# ---------------------------------------------------------------------------
def _wait_and_maybe_quit(video, idx, start_wall, realtime):
    """Show frame for the right duration; return True if user pressed q/ESC."""
    if realtime:
        target = start_wall + video.frame_to_time(idx)
        delay_ms = max(1, int((target - time.time()) * 1000))
    else:
        delay_ms = 1
    key = cv2.waitKey(delay_ms) & 0xFF
    return key in (ord("q"), 27)


# ---------------------------------------------------------------------------
# overlay
# ---------------------------------------------------------------------------
def _draw_overlay(frame, field, cell, homography, timestamp):
    disp = frame.copy()
    h, w = disp.shape[:2]

    # Field outline from calibration corners (pixel space).
    if homography is not None and homography.corners:
        pts = np.array(homography.corners, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(disp, [pts], True, (0, 200, 255), 2)

    # 4x5 grid drawn in image space using the inverse homography, so it lines
    # up with the actual field. Falls back to a plain screen grid if no calib.
    _draw_grid(disp, homography, cell, w, h)

    # Ball marker (map normalized back to pixels if we can).
    if field is not None and homography is not None:
        px = _field_to_pixel(homography, field)
        if px is not None:
            cv2.circle(disp, px, 8, (0, 0, 255), -1)
            cv2.circle(disp, px, 10, (255, 255, 255), 2)

    # HUD text.
    cv2.putText(disp, f"t={timestamp:.2f}s", (12, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    if cell is not None:
        cv2.putText(disp, f"Row {cell[0]}  Column {cell[1]}", (12, 54),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return disp


def _draw_grid(disp, homography, active_cell, w, h):
    for r in range(1, GRID_ROWS + 1):
        for c in range(1, GRID_COLS + 1):
            # cell corners in normalized space
            x0, x1 = (c - 1) / GRID_COLS, c / GRID_COLS
            y0, y1 = (r - 1) / GRID_ROWS, r / GRID_ROWS
            corners_n = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            if homography is not None:
                poly = [_field_to_pixel(homography, p) for p in corners_n]
                if any(p is None for p in poly):
                    continue
                poly = np.array(poly, dtype=np.int32).reshape(-1, 1, 2)
            else:
                poly = np.array(
                    [(int(x * w), int(y * h)) for x, y in corners_n],
                    dtype=np.int32,
                ).reshape(-1, 1, 2)
            highlight = active_cell == (r, c)
            color = (0, 255, 0) if highlight else (80, 80, 80)
            thick = 3 if highlight else 1
            cv2.polylines(disp, [poly], True, color, thick)


def _field_to_pixel(homography, field):
    """Inverse of homography: normalized field (u, v) -> pixel (x, y)."""
    inv = np.linalg.inv(homography.matrix)
    u, v = field
    pt = np.array([u, v, 1.0])
    x, y, wgt = inv @ pt
    if wgt == 0:
        return None
    return int(x / wgt), int(y / wgt)
