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
# Processing / performance
#   Processing efficiency is a top priority. We only ever need to know which
#   of GRID_ROWS x GRID_COLS large regions contains the ball, so we downscale
#   aggressively and can skip frames.
# ---------------------------------------------------------------------------
PROCESS_WIDTH = 640          # width used for tracking (frame is scaled down)
PROCESS_EVERY_N_FRAMES = 2   # run the tracker every Nth frame, interpolate rest

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
