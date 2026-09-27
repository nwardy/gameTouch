"""Shared goal-mouth geometry for manual annotation and celebration output."""

from config import (
    FIELD_LENGTH_METERS,
    FIELD_WIDTH_METERS,
    GOAL_MOUTH_WIDTH_METERS,
    GOAL_NET_DEPTH_METERS,
)


def is_goal_position(field):
    """Return whether normalized coordinates lie inside either visible net.

    The pitch itself is 0..1 in x. Goal-net clicks are accepted up to three
    metres beyond either goal line, but only within the 7.32 m goal mouth.
    """
    if field is None:
        return False
    u, v = field
    x = u * FIELD_LENGTH_METERS
    y = v * FIELD_WIDTH_METERS
    half_mouth = GOAL_MOUTH_WIDTH_METERS / 2
    in_mouth = FIELD_WIDTH_METERS / 2 - half_mouth <= y <= FIELD_WIDTH_METERS / 2 + half_mouth
    return in_mouth and (
        -GOAL_NET_DEPTH_METERS <= x < 0
        or FIELD_LENGTH_METERS < x <= FIELD_LENGTH_METERS + GOAL_NET_DEPTH_METERS
    )


def nearest_goal_net_position(field):
    """Place an explicitly marked goal at the center of its visible net.

    A homography maps the grass plane, not a raised goal net. The user still
    clicks the real ball, but this explicit event needs a stable, renderable
    point that is visibly beyond the nearest goal line.
    """
    u, _v = field
    net_u = GOAL_NET_DEPTH_METERS / FIELD_LENGTH_METERS
    return (-net_u, 0.5) if u <= 0.5 else (1.0 + net_u, 0.5)
