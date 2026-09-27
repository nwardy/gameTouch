"""
Global configuration for the tactile sports-field system.

Keep this lightweight. Hardware-specific relay configuration lives in
tactile/relay_config.py so it stays centralized next to the relay code.
"""

# ---------------------------------------------------------------------------
# Grid geometry
# ---------------------------------------------------------------------------
GRID_ROWS = 4       # rows 1..4  (top sideline -> bottom sideline, y axis)
GRID_COLS = 5       # cols 1..5  (left edge -> right edge, x axis)

# ---------------------------------------------------------------------------
# Soccer pitch coordinates
# ---------------------------------------------------------------------------
# The screenshot uses a standard full-size pitch. Vision works in metres,
# then normalizes positions for the tactile grid. A saved calibration is valid
# only for this fixed camera view and zoom.
FIELD_NAME = "soccer pitch"
FIELD_LENGTH_METERS = 105.0
FIELD_WIDTH_METERS = 68.0
FIELD_UNIT_LABEL = "m"
GOAL_MOUTH_WIDTH_METERS = 7.32
GOAL_NET_DEPTH_METERS = 3.0
GOAL_CELEBRATION_DELAY_SECONDS = 0.3
GOAL_CELEBRATION_BLINK_SECONDS = 0.15
GOAL_CELEBRATION_BLINKS = 3

# ---------------------------------------------------------------------------
# Processing / performance
#   Processing efficiency is a top priority. We only ever need to know which
#   of GRID_ROWS x GRID_COLS large regions contains the ball, so we downscale
#   aggressively and can skip frames.
# ---------------------------------------------------------------------------
PROCESS_WIDTH = 640          # width used for tracking (frame is scaled down)
PROCESS_EVERY_N_FRAMES = 2   # run the tracker every Nth frame, interpolate rest
# Do not invent a long path through an occlusion or tracker re-acquisition.
MAX_INTERPOLATION_GAP_SECONDS = 0.25
# A manual click is an intentional annotation, so it can safely cover a longer
# interval than an uncertain automatic tracker result.
MANUAL_PATH_MAX_INTERPOLATION_GAP_SECONDS = 1.0

# ---------------------------------------------------------------------------
# White-ball guard
# ---------------------------------------------------------------------------
# A small white soccer ball and a white shirt confuse a generic appearance
# tracker. Pixel limits are expressed for a 1280x720 source and scaled at
# runtime. They are deliberately a guard/reacquisition hint, not a detector.
BALL_WHITE_MIN_PIXELS = 3
BALL_WHITE_MAX_PIXELS = 120
PLAYER_WHITE_COMPONENT_MIN_PIXELS = 180
WHITE_PIXEL_MAX_SATURATION = 80
WHITE_PIXEL_MIN_VALUE = 150

# ---------------------------------------------------------------------------
# Trajectory smoothing + tactile cell debounce (see tactile/grid_mapper.py)
# ---------------------------------------------------------------------------
EMA_ALPHA = 0.4              # exponential moving average factor for smoothing
                             #   higher = more responsive, lower = smoother
DEBOUNCE_FRAMES = 3          # a new cell must persist this many samples before
                             #   we actually switch to it (anti-chatter)
HYSTERESIS = 0.04            # normalized margin the ball must cross past a cell
                             #   boundary before the cell is allowed to change

# ---------------------------------------------------------------------------
# Debug / logging
# ---------------------------------------------------------------------------
DEBUG_VISUAL = True          # draw overlay window during playback
LOG_ON_CHANGE_ONLY = True    # only print tracking lines when the cell changes

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALIBRATION_DIR = os.path.join(BASE_DIR, "data", "calibration")
TRAJECTORY_DIR = os.path.join(BASE_DIR, "data", "trajectories")
