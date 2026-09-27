"""Render ball motion and its active 4x5 tactile sensor to an MP4."""

import os

import cv2
import numpy as np

from config import (
    FIELD_LENGTH_METERS,
    FIELD_WIDTH_METERS,
    FIELD_UNIT_LABEL,
    GRID_COLS,
    GRID_ROWS,
    GOAL_CELEBRATION_BLINKS,
    GOAL_CELEBRATION_BLINK_SECONDS,
    GOAL_CELEBRATION_DELAY_SECONDS,
    GOAL_MOUTH_WIDTH_METERS,
    GOAL_NET_DEPTH_METERS,
)
from tactile.grid_mapper import field_to_cell
from tracking.goal_detection import is_goal_position
from sports import get_sport


_FIELD_MARGIN = 28
_BACKGROUND = (24, 27, 33)
_TURF = (47, 122, 71)
_LINE = (224, 236, 226)
_TEXT = (245, 247, 250)
_BALL = (0, 145, 255)
_TRAIL = (54, 158, 241)
_SENSOR_OFF = (83, 92, 102)
_SENSOR_ON = (70, 220, 255)
_SENSOR_RING = (235, 248, 252)
_GRID_LINE = (126, 167, 138)


def render_birdseye_video(video, position_source, output_path, speed=1.0, sport="soccer"):
    """Write an MP4 showing ball position and the active tactile sensor.

    A ``None`` position intentionally produces no ball marker, preventing a
    lost track from being displayed as a real location. Its most recent sensor
    remains highlighted during that gap, matching the tactile board's hold
    behavior. ``speed`` changes only playback speed.
    """
    output_path = next_available_output_path(output_path)

    canvas_width = max(video.width, 640)
    profile = get_sport(sport)
    field_height = canvas_width * profile.width_meters / profile.length_meters
    canvas_height = int(field_height + 2 * _FIELD_MARGIN + 64)
    if speed <= 0:
        raise ValueError("bird's-eye speed must be greater than zero")
    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        max(1.0, video.fps * speed),
        (canvas_width, canvas_height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"could not open video writer for {output_path}")

    trail = []
    held_cell = None
    goal_point = None
    goal_cell = None
    try:
        while True:
            index, frame = video.read_next()
            if frame is None:
                break

            timestamp = video.frame_to_time(index)
            position = position_source.get_position(timestamp)
            canvas, field_rect = _draw_field(canvas_width, canvas_height, sport=sport)
            active_cell = held_cell
            point = None

            if position is not None:
                point = _field_point(position, field_rect)
                if point is not None:
                    active_cell = field_to_cell(*position)
                    held_cell = active_cell
                    if is_goal_position(position):
                        goal_point = point
                        goal_cell = active_cell
            _draw_sensor_grid(canvas, field_rect, active_cell)
            if point is not None:
                trail.append(point)
                _draw_trail(canvas, trail)
                cv2.circle(canvas, point, 8, _BALL, -1, lineType=cv2.LINE_AA)
                cv2.circle(canvas, point, 10, _TEXT, 2, lineType=cv2.LINE_AA)

            _draw_hud(canvas, timestamp, position, active_cell)
            writer.write(canvas)
        if goal_point is not None:
            _write_goal_celebration(
                writer, canvas_width, canvas_height, trail, goal_point, goal_cell,
                output_fps=max(1.0, video.fps * speed),
            )
    finally:
        writer.release()
    return output_path


def next_available_output_path(requested_path):
    """Return an unused MP4 path without replacing a previous export."""
    directory = os.path.dirname(requested_path) or "."
    os.makedirs(directory, exist_ok=True)
    if not os.path.exists(requested_path):
        return requested_path

    stem, extension = os.path.splitext(requested_path)
    for version in range(1, 10_000):
        candidate = f"{stem}-{version:03d}{extension}"
        if not os.path.exists(candidate):
            return candidate
    raise RuntimeError("could not find an unused output filename")


def _draw_field(width, height, sport="soccer"):
    canvas = np.full((height, width, 3), _BACKGROUND, dtype=np.uint8)
    x0, x1 = _FIELD_MARGIN, width - _FIELD_MARGIN
    y0, y1 = 64, height - _FIELD_MARGIN
    cv2.rectangle(canvas, (x0, y0), (x1, y1), _TURF, -1)
    cv2.rectangle(canvas, (x0, y0), (x1, y1), _LINE, 2)

    if sport.startswith("tennis"):
        _draw_tennis_markings(canvas, (x0, y0, x1, y1))
    else:
        _draw_pitch_markings(canvas, (x0, y0, x1, y1))
        _draw_goal_nets(canvas, (x0, y0, x1, y1))

    return canvas, (x0, y0, x1, y1)


def _draw_sensor_grid(canvas, field_rect, active_cell, all_active=False):
    """Draw 20 physical-board sensor positions; highlight the nearest one."""
    x0, y0, x1, y1 = field_rect
    # The 5x4 board grid is visible over the real soccer-field markings.
    for column in range(1, GRID_COLS):
        x = round(x0 + column / GRID_COLS * (x1 - x0))
        cv2.line(canvas, (x, y0), (x, y1), _GRID_LINE, 1, cv2.LINE_AA)
    for row in range(1, GRID_ROWS):
        y = round(y0 + row / GRID_ROWS * (y1 - y0))
        cv2.line(canvas, (x0, y), (x1, y), _GRID_LINE, 1, cv2.LINE_AA)
    for row in range(1, GRID_ROWS + 1):
        for column in range(1, GRID_COLS + 1):
            x = round(x0 + (column - 0.5) / GRID_COLS * (x1 - x0))
            y = round(y0 + (row - 0.5) / GRID_ROWS * (y1 - y0))
            is_active = all_active or active_cell == (row, column)
            color = _SENSOR_ON if is_active else _SENSOR_OFF
            radius = 13 if is_active else 9
            if is_active:
                cv2.circle(canvas, (x, y), radius + 5, _SENSOR_RING, 2,
                           lineType=cv2.LINE_AA)
            cv2.circle(canvas, (x, y), radius, color, -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (x, y), radius, _SENSOR_RING, 1,
                       lineType=cv2.LINE_AA)
            cv2.putText(canvas, f"{row},{column}", (x - 13, y + 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, _TEXT, 1,
                        cv2.LINE_AA)


def _field_point(position, field_rect):
    x, y = position
    extra_x = 3.0 / FIELD_LENGTH_METERS
    if not (-extra_x <= x <= 1.0 + extra_x and 0.0 <= y <= 1.0):
        return None
    x0, y0, x1, y1 = field_rect
    return round(x0 + x * (x1 - x0)), round(y0 + y * (y1 - y0))


def _draw_pitch_markings(canvas, field_rect):
    """Restore the recognizable soccer field beneath the tactile overlay."""
    x0, y0, x1, y1 = field_rect

    def point(x_meters, y_meters):
        return (
            round(x0 + x_meters / FIELD_LENGTH_METERS * (x1 - x0)),
            round(y0 + y_meters / FIELD_WIDTH_METERS * (y1 - y0)),
        )

    halfway_x = point(FIELD_LENGTH_METERS / 2, 0)[0]
    cv2.line(canvas, (halfway_x, y0), (halfway_x, y1), _LINE, 2, cv2.LINE_AA)
    center = point(FIELD_LENGTH_METERS / 2, FIELD_WIDTH_METERS / 2)
    radius = round(9.15 / FIELD_LENGTH_METERS * (x1 - x0))
    cv2.circle(canvas, center, radius, _LINE, 2, cv2.LINE_AA)
    cv2.circle(canvas, center, 3, _LINE, -1, cv2.LINE_AA)

    _draw_box(canvas, point, 0, 16.5, 40.32)
    _draw_box(canvas, point, FIELD_LENGTH_METERS - 16.5, 16.5, 40.32)
    _draw_box(canvas, point, 0, 5.5, 18.32)
    _draw_box(canvas, point, FIELD_LENGTH_METERS - 5.5, 5.5, 18.32)
    for x_meters in (11, FIELD_LENGTH_METERS - 11):
        cv2.circle(canvas, point(x_meters, FIELD_WIDTH_METERS / 2), 3, _LINE,
                   -1, cv2.LINE_AA)


def _draw_box(canvas, point, x_start, depth, width):
    y_start = (FIELD_WIDTH_METERS - width) / 2
    cv2.rectangle(canvas, point(x_start, y_start),
                  point(x_start + depth, y_start + width), _LINE, 2,
                  cv2.LINE_AA)


def _draw_tennis_markings(canvas, field_rect):
    """A doubles tennis court beneath the same 4x5 tactile sensor grid."""
    x0, y0, x1, y1 = field_rect
    net_x = round((x0 + x1) / 2)
    cv2.line(canvas, (net_x, y0), (net_x, y1), _LINE, 2, cv2.LINE_AA)
    # Service lines sit 6.40 m from the net on a 23.77 m court.
    service_offset = 6.40 / 23.77 * (x1 - x0)
    for x in (round(net_x - service_offset), round(net_x + service_offset)):
        cv2.line(canvas, (x, y0), (x, y1), _LINE, 1, cv2.LINE_AA)
    # Singles sidelines (8.23 m) inside doubles sidelines (10.97 m).
    inset = (10.97 - 8.23) / 2 / 10.97 * (y1 - y0)
    for y in (round(y0 + inset), round(y1 - inset)):
        cv2.line(canvas, (x0, y), (x1, y), _LINE, 1, cv2.LINE_AA)


def _draw_goal_nets(canvas, field_rect):
    """Draw shallow nets outside each goal line so a scored ball is visible."""
    x0, y0, x1, y1 = field_rect
    field_width_px = x1 - x0
    net_depth = round(GOAL_NET_DEPTH_METERS / FIELD_LENGTH_METERS * field_width_px)
    mouth_half = round(GOAL_MOUTH_WIDTH_METERS / FIELD_WIDTH_METERS * (y1 - y0) / 2)
    center_y = round((y0 + y1) / 2)
    for goal_x, net_x in ((x0, x0 - net_depth), (x1, x1 + net_depth)):
        cv2.rectangle(canvas, (min(goal_x, net_x), center_y - mouth_half),
                      (max(goal_x, net_x), center_y + mouth_half), _LINE, 1,
                      cv2.LINE_AA)


def _draw_trail(canvas, trail):
    if len(trail) < 2:
        return
    points = np.array(trail[-180:], dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(canvas, [points], False, _TRAIL, 2, lineType=cv2.LINE_AA)


def _write_goal_celebration(writer, width, height, trail, goal_point, goal_cell,
                             output_fps):
    """Append an unambiguous netted-goal cue after the final video frame."""
    field_canvas, field_rect = _draw_field(width, height)
    hold_frames = max(1, round(GOAL_CELEBRATION_DELAY_SECONDS * output_fps))
    blink_frames = max(1, round(GOAL_CELEBRATION_BLINK_SECONDS * output_fps))
    for _ in range(hold_frames):
        writer.write(_draw_goal_frame(field_canvas, field_rect, trail, goal_point,
                                      goal_cell, all_active=False))
    for _ in range(GOAL_CELEBRATION_BLINKS):
        for _ in range(blink_frames):
            writer.write(_draw_goal_frame(field_canvas, field_rect, trail, goal_point,
                                          goal_cell, all_active=True))
        for _ in range(blink_frames):
            writer.write(_draw_goal_frame(field_canvas, field_rect, trail, goal_point,
                                          goal_cell, all_active=False))


def _draw_goal_frame(field_canvas, field_rect, trail, goal_point, goal_cell,
                     all_active):
    canvas = field_canvas.copy()
    _draw_sensor_grid(canvas, field_rect, goal_cell, all_active=all_active)
    _draw_trail(canvas, trail)
    cv2.circle(canvas, goal_point, 9, _BALL, -1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, goal_point, 12, _TEXT, 2, lineType=cv2.LINE_AA)
    headline = "GOAL! ALL SENSORS ON" if all_active else "GOAL!"
    cv2.putText(canvas, headline, (28, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                _SENSOR_ON, 2, cv2.LINE_AA)
    cv2.putText(canvas, "Ball in net — celebration follows", (28, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, _TEXT, 1, cv2.LINE_AA)
    return canvas


def _draw_hud(canvas, timestamp, position, active_cell):
    cv2.putText(canvas, "Tactile board — 4 rows x 5 columns", (28, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, _TEXT, 2, cv2.LINE_AA)
    if position is None:
        if active_cell is None:
            status = f"t={timestamp:.2f}s  ball: unknown  sensor: OFF"
        else:
            status = (
                f"t={timestamp:.2f}s  ball: lost  HOLDING: row "
                f"{active_cell[0]}, column {active_cell[1]}"
            )
    else:
        x, y = position
        status = (
            f"t={timestamp:.2f}s  x={x * FIELD_LENGTH_METERS:.1f} {FIELD_UNIT_LABEL}  "
            f"y={y * FIELD_WIDTH_METERS:.1f} {FIELD_UNIT_LABEL}  "
            f"ACTIVE: row {active_cell[0]}, column {active_cell[1]}"
        )
    cv2.putText(canvas, status, (28, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                _TEXT, 1, cv2.LINE_AA)
