"""Short, distinct soccer-event patterns for the existing 4x5 tactile board."""

import time


EVENT_DESCRIPTIONS = {
    "goal": "three full-board celebration blinks",
    "yellow_card": "two short taps at the ball cell",
    "red_card": "two long full-board alerts",
    "offside": "short then long tap at the ball cell",
    "penalty_awarded": "one long plus two short taps at the ball cell",
    "corner_kick": "four quick taps at the ball cell",
    "substitution": "one long and one short tap at the ball cell",
    "var_review": "two slow taps at the ball cell",
}


def description_for(event):
    return EVENT_DESCRIPTIONS.get(event, "no tactile event pattern")


def run_event_pattern(output, event, cell, sleep=time.sleep):
    """Play a short event alert, then yield the board back to ball tracking."""
    if event not in EVENT_DESCRIPTIONS or (event != "goal" and cell is None):
        return False
    if event == "goal":
        _full_board(output, 0.20, 3, sleep)
    elif event == "red_card":
        _full_board(output, 0.55, 2, sleep)
    elif event == "yellow_card":
        _cell_taps(output, cell, [0.18, 0.18], sleep)
    elif event == "offside":
        _cell_taps(output, cell, [0.12, 0.42], sleep)
    elif event == "penalty_awarded":
        _cell_taps(output, cell, [0.50, 0.14, 0.14], sleep)
    elif event == "corner_kick":
        _cell_taps(output, cell, [0.11, 0.11, 0.11, 0.11], sleep)
    elif event == "substitution":
        _cell_taps(output, cell, [0.42, 0.14], sleep)
    elif event == "var_review":
        _cell_taps(output, cell, [0.38, 0.38], sleep)
    return True


def _full_board(output, on_seconds, repeats, sleep):
    for _ in range(repeats):
        output.all_on()
        sleep(on_seconds)
        output.all_off()
        sleep(0.16)


def _cell_taps(output, cell, durations, sleep):
    for on_seconds in durations:
        output.set_cell(*cell)
        sleep(on_seconds)
        output.all_off()
        sleep(0.16)
