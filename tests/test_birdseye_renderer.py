"""Visual mapping tests for the tactile-board MP4 renderer."""

from video.birdseye_renderer import (
    _SENSOR_ON,
    _draw_field,
    _draw_pitch_markings,
    _draw_sensor_grid,
    _field_point,
)


def test_active_sensor_is_drawn_at_its_4_by_5_grid_center():
    canvas, field = _draw_field(800, 600)
    _draw_sensor_grid(canvas, field, active_cell=(2, 4))
    x0, y0, x1, y1 = field
    x = round(x0 + (4 - 0.5) / 5 * (x1 - x0))
    y = round(y0 + (2 - 0.5) / 4 * (y1 - y0))
    assert tuple(canvas[y, x]) == _SENSOR_ON


def test_goal_blink_marks_all_twenty_sensor_centers_active():
    canvas, field = _draw_field(800, 600)
    _draw_sensor_grid(canvas, field, active_cell=None, all_active=True)
    x0, y0, x1, y1 = field
    for row in range(1, 5):
        for column in range(1, 6):
            x = round(x0 + (column - 0.5) / 5 * (x1 - x0))
            y = round(y0 + (row - 0.5) / 4 * (y1 - y0))
            assert tuple(canvas[y, x]) == _SENSOR_ON


def test_soccer_field_markings_are_retained_beneath_sensor_grid():
    canvas, field = _draw_field(800, 600)
    _draw_pitch_markings(canvas, field)
    x0, y0, x1, y1 = field
    center = (round((x0 + x1) / 2), round((y0 + y1) / 2))
    # The center spot is the bright field-line color, not plain turf.
    assert tuple(canvas[center[1], center[0]]) != (47, 122, 71)


def test_goal_net_position_can_be_rendered_outside_the_pitch_boundary():
    _, field = _draw_field(800, 600)
    point = _field_point((-2 / 105, 0.5), field)
    assert point is not None
    assert point[0] < field[0]
