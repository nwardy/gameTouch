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
from tactile.event_patterns import description_for, run_event_pattern
from config import (
    FIELD_LENGTH_METERS,
    FIELD_WIDTH_METERS,
    GRID_ROWS,
    GRID_COLS,
    EMA_ALPHA,
    DEBUG_VISUAL,
    LOG_ON_CHANGE_ONLY,
    GOAL_CELEBRATION_BLINKS,
    GOAL_CELEBRATION_BLINK_SECONDS,
    GOAL_CELEBRATION_DELAY_SECONDS,
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


def play(video, position_source, tactile_output, calibration=None,
         debug=DEBUG_VISUAL, realtime=True, fan_pulse=None, sport="soccer"):
    """Play `video` in sync with `position_source`, driving `tactile_output`.

    Returns normally at end of clip. Caller is responsible for tactile cleanup
    (so relays are always turned off even on Ctrl+C).
    """
    smoother = _EMA()
    debouncer = CellDebouncer()
    last_logged_cell = None
    window = "Tactile Field - debug"

    start_wall = time.time()
    completed = False
    previous_timestamp = -0.001
    last_fan_update = None
    while True:
        idx, frame = video.read_next()
        if frame is None:
            completed = True
            break
        timestamp = video.frame_to_time(idx)

        if sport.startswith("tennis"):
            for event in _events_between(position_source, previous_timestamp, timestamp):
                tactile_output.pulse_side(event["side"])
        previous_timestamp = timestamp

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

        pulse = fan_pulse.latest() if fan_pulse else None
        if pulse and pulse.updated_at != last_fan_update and pulse.event not in (None, "none"):
            last_fan_update = pulse.updated_at
            if pulse.event_confidence in ("medium", "high"):
                if run_event_pattern(tactile_output, pulse.event, cell):
                    print(f"TACTILE EVENT: {pulse.event} — {description_for(pulse.event)}")
            else:
                print(f"Grok event not pulsed: {pulse.event} has low confidence.")

        if debug:
            homography = _homography_for(calibration, frame, timestamp)
            disp = _draw_overlay(frame, field, cell, homography, timestamp, pulse)
            cv2.imshow(window, disp)
            # pace to real time relative to video fps
            action = _wait_for_action(video, idx, start_wall, realtime)
            if action == "quit":
                break
            if action == "fan" and fan_pulse:
                if not fan_pulse.request_refresh():
                    print("Fan pulse is already checking posts.")

    if debug:
        cv2.destroyWindow(window)
    if completed and _goal_time(position_source) is not None:
        _celebrate_goal(tactile_output)


def _goal_time(position_source):
    getter = getattr(position_source, "goal_time", None)
    return getter() if getter else None


def _events_between(position_source, start_time, end_time):
    getter = getattr(position_source, "events_between", None)
    return getter(start_time, end_time) if getter else []


def _celebrate_goal(tactile_output):
    """Wait, then flash every sensor three times after a manual goal point."""
    time.sleep(GOAL_CELEBRATION_DELAY_SECONDS)
    for _ in range(GOAL_CELEBRATION_BLINKS):
        tactile_output.all_on()
        time.sleep(GOAL_CELEBRATION_BLINK_SECONDS)
        tactile_output.all_off()
        time.sleep(GOAL_CELEBRATION_BLINK_SECONDS)


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
def _wait_for_action(video, idx, start_wall, realtime):
    """Show frame for the right duration; return quit, fan, or None."""
    if realtime:
        target = start_wall + video.frame_to_time(idx)
        delay_ms = max(1, int((target - time.time()) * 1000))
    else:
        delay_ms = 1
    key = cv2.waitKey(delay_ms) & 0xFF
    if key in (ord("q"), 27):
        return "quit"
    if key in (ord("f"), ord("F")):
        return "fan"
    return None


# ---------------------------------------------------------------------------
# overlay
# ---------------------------------------------------------------------------
def _draw_overlay(frame, field, cell, homography, timestamp, fan_pulse=None):
    disp = frame.copy()
    h, w = disp.shape[:2]

    # Field outline from calibration corners (pixel space).
    if homography is not None and homography.corners:
        pts = np.array(homography.corners, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(disp, [pts], True, (0, 200, 255), 2)

    # 4x5 grid drawn in image space using the inverse homography, so it lines
    # up with the actual field. Falls back to a plain screen grid if no calib.
    _draw_yard_grid(disp, homography)
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
    if field is not None:
        cv2.putText(disp,
                    f"ball: {field[0] * FIELD_LENGTH_METERS:.1f} m, "
                    f"{field[1] * FIELD_WIDTH_METERS:.1f} m across",
                    (12, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 220, 255), 2)
    if fan_pulse is not None:
        _draw_fan_pulse(disp, fan_pulse, h)
    return disp


def _draw_fan_pulse(disp, pulse, frame_height):
    """Render a compact readable fan summary for the video debug view."""
    if pulse.intensity is None:
        heading = "FAN PULSE: ready — press F to ask"
        color = (185, 185, 185)
    else:
        heading = f"FAN INTENSITY: {pulse.intensity}/100 ({pulse.level.upper()})"
        color = {"quiet": (140, 220, 130), "building": (80, 210, 245),
                 "high": (60, 150, 255), "urgent": (70, 70, 255)}.get(pulse.level, (255, 255, 255))
    event_line = "No confirmed soccer event." if pulse.event in (None, "none") else (
        f"Grok event: {pulse.event.replace('_', ' ')} — {description_for(pulse.event)}."
    )
    words = f"{event_line} Game: {pulse.game_context or 'Checking live game context.'} Crowd: {pulse.text}".split()
    lines, line = [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > 70:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    lines = lines[:3]
    y = max(110, frame_height - 18 * (len(lines) + 1) - 18)
    cv2.rectangle(disp, (6, y - 18), (min(disp.shape[1] - 6, 770), frame_height - 6), (20, 20, 20), -1)
    cv2.putText(disp, heading, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2)
    y += 18
    for line in lines:
        cv2.putText(disp, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        y += 18


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


def _draw_yard_grid(disp, homography):
    """Draw 10-yard field lines in the source video for calibration QA."""
    if homography is None:
        return
    for meter in range(0, int(FIELD_LENGTH_METERS) + 1, 10):
        u = meter / FIELD_LENGTH_METERS
        start = _field_to_pixel(homography, (u, 0.0))
        end = _field_to_pixel(homography, (u, 1.0))
        if start is None or end is None:
            continue
        cv2.line(disp, start, end, (110, 90, 20), 1)
        cv2.putText(disp, str(meter), start, cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (110, 90, 20), 1)


def _field_to_pixel(homography, field):
    """Inverse of homography: normalized field (u, v) -> pixel (x, y)."""
    inv = np.linalg.inv(homography.matrix)
    u, v = field
    pt = np.array([u, v, 1.0])
    x, y, wgt = inv @ pt
    if wgt == 0:
        return None
    return int(x / wgt), int(y / wgt)


def _homography_for(calibration, frame, timestamp):
    if calibration is None:
        return None
    if hasattr(calibration, "homography_for"):
        return calibration.homography_for(frame, timestamp)
    return calibration.homography_at(timestamp)
