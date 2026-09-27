"""Geometry tests for manual soccer-pitch landmark calibration."""

import numpy as np
import cv2

from calibration.adaptive_calibration import AdaptiveCalibration
from calibration.calibration_timeline import CalibrationTimeline
from calibration.homography import FieldHomography
from config import FIELD_WIDTH_METERS
from tracking.ball_tracker import (
    _box_centered_at,
    _find_small_moving_white_ball,
    _is_player_sized_white_target,
)
from tracking.goal_detection import is_goal_position, nearest_goal_net_position
from tracking.prerecorded_source import PrerecordedSource


def test_landmark_calibration_maps_to_pitch_meters():
    # Four corners plus a halfway-line landmark from a synthetic camera.
    # This simple camera is rectangular so the expected center is exact.
    image_points = [
        (0, 0),
        (1000, 0),
        (1000, 647.619),
        (0, 647.619),
        (500, 323.8095),
    ]
    field_points = [
        (0, 0),
        (105, 0),
        (105, FIELD_WIDTH_METERS),
        (0, FIELD_WIDTH_METERS),
        (52.5, FIELD_WIDTH_METERS / 2),
    ]
    homography = FieldHomography.from_correspondences(image_points, field_points)

    x_meters, y_meters = homography.pixel_to_meters(500, 323.8095)
    assert np.isclose(x_meters, 52.5, atol=0.01)
    assert np.isclose(y_meters, FIELD_WIDTH_METERS / 2, atol=0.01)
    assert max(homography.calibration_error_meters()) < 0.01


def test_off_field_point_is_rejected():
    homography = FieldHomography.from_corners(
        [(0, 0), (100, 0), (100, 100), (0, 100)]
    )
    assert FieldHomography.is_on_field(homography.pixel_to_field(50, 50))
    assert not FieldHomography.is_on_field(homography.pixel_to_field(200, 50))


def test_calibration_timeline_switches_only_after_marked_shift(tmp_path):
    before_shift = FieldHomography.from_corners(
        [(0, 0), (100, 0), (100, 100), (0, 100)]
    )
    after_shift = FieldHomography.from_corners(
        [(10, 0), (110, 0), (110, 100), (10, 100)]
    )
    timeline = CalibrationTimeline.single(before_shift)
    timeline.add_shift(4.5, after_shift)

    assert timeline.homography_at(4.499).pixel_to_field(50, 50) == (0.5, 0.5)
    assert timeline.homography_at(4.5).pixel_to_field(60, 50) == (0.5, 0.5)

    path = tmp_path / "two_view.json"
    timeline.save(path)
    loaded = CalibrationTimeline.load(path)
    assert len(loaded.segments) == 2
    assert loaded.homography_at(4.5).pixel_to_field(60, 50) == (0.5, 0.5)


def test_calibration_timeline_loads_existing_single_view_file(tmp_path):
    homography = FieldHomography.from_corners(
        [(0, 0), (100, 0), (100, 100), (0, 100)]
    )
    path = tmp_path / "old_calibration.json"
    homography.save(path)

    timeline = CalibrationTimeline.load(path)
    assert len(timeline.segments) == 1
    assert timeline.homography_at(99).pixel_to_field(50, 50) == (0.5, 0.5)


def test_reacquisition_box_reuses_size_and_stays_inside_frame():
    box = _box_centered_at((2, 98), (10, 10, 20, 10), (100, 120, 3))
    assert box == (0, 90, 20, 10)


def test_adaptive_calibration_compensates_for_small_camera_translation():
    reference = np.zeros((200, 200, 3), dtype=np.uint8)
    landmarks = [(20, 20), (180, 20), (180, 180), (20, 180)]
    for point in landmarks:
        cv2.circle(reference, point, 6, (255, 255, 255), -1)
    shifted = cv2.warpAffine(
        reference, np.float32([[1, 0, 3], [0, 1, 2]]), (200, 200)
    )
    homography = FieldHomography.from_correspondences(
        landmarks, [(0, 0), (105, 0), (105, 68), (0, 68)]
    )
    timeline = CalibrationTimeline.single(homography)

    class FakeVideo:
        def time_to_frame(self, _seconds):
            return 0

        def read_frame(self, _index):
            return reference.copy()

    adaptive = AdaptiveCalibration(FakeVideo(), timeline)
    updated = adaptive.homography_for(shifted, 0.1)
    x_meters, y_meters = updated.pixel_to_meters(103, 102)
    assert adaptive.last_inlier_count == 4
    assert np.isclose(x_meters, 52.5, atol=0.1)
    assert np.isclose(y_meters, 34, atol=0.1)


def test_white_shirt_guard_prefers_small_moving_ball():
    previous = np.zeros((100, 200, 3), dtype=np.uint8)
    current = previous.copy()
    cv2.rectangle(current, (20, 20), (50, 50), (255, 255, 255), -1)
    cv2.circle(previous, (80, 60), 1, (255, 255, 255), -1)
    cv2.circle(current, (86, 60), 1, (255, 255, 255), -1)

    assert _is_player_sized_white_target(current, (35, 35))
    candidate = _find_small_moving_white_ball(previous, current, (35, 35), 70)
    assert candidate is not None
    assert np.allclose(candidate, (86, 60), atol=1)


def test_goal_net_coordinates_are_accepted_but_sideline_coordinates_are_not():
    # 2 m behind either goal line, centered in its 7.32 m mouth.
    assert is_goal_position((-2 / 105, 0.5))
    assert is_goal_position(((105 + 2) / 105, 0.5))
    assert not is_goal_position((-2 / 105, 0.1))


def test_explicit_goal_click_is_mapped_into_nearest_net_for_rendering():
    assert nearest_goal_net_position((0.12, 0.8))[0] < 0
    assert nearest_goal_net_position((0.88, 0.2))[0] > 1


def test_tennis_calibration_uses_tennis_court_dimensions():
    homography = FieldHomography.from_correspondences(
        [(0, 0), (100, 0), (100, 100), (0, 100)],
        [(0, 0), (23.77, 0), (23.77, 10.97), (0, 10.97)],
        sport="tennis", field_length_meters=23.77, field_width_meters=10.97,
    )
    assert np.allclose(homography.pixel_to_meters(50, 50), (11.885, 5.485))


def test_manual_points_interpolate_across_deliberate_longer_gap():
    source = PrerecordedSource([
        {"time": 0.0, "x": 0.2, "y": 0.3, "source": "manual_path"},
        {"time": 0.8, "x": 0.6, "y": 0.7, "source": "manual_path"},
    ])
    assert source.get_position(0.4) == (0.4, 0.5)


def test_automatic_tracker_gaps_remain_unknown():
    source = PrerecordedSource([
        {"time": 0.0, "x": 0.2, "y": 0.3, "source": "manual_tracker"},
        {"time": 0.8, "x": 0.6, "y": 0.7, "source": "manual_tracker"},
    ])
    assert source.get_position(0.4) is None
