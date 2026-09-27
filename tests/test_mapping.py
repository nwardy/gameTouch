"""
Unit tests that run on any machine (no GPIO hardware required).

Covered:
  * normalized coordinate -> grid cell, including corners and boundaries
  * invalid / out-of-range values are clamped, never producing invalid cells
  * relay polarity conversion (active-low vs active-high)
  * requesting the same cell repeatedly does not re-toggle relays
  * a cell transition performs OFF -> short delay -> new row + new column

Run:  python3 -m pytest tests/test_mapping.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tactile.grid_mapper import field_to_cell, cell_to_center, CellDebouncer
from tactile.relay_config import ROW_PINS, COLUMN_PINS


# ---------------------------------------------------------------------------
# coordinate -> grid
# ---------------------------------------------------------------------------
def test_corners():
    assert field_to_cell(0.0, 0.0) == (1, 1)
    assert field_to_cell(0.99, 0.99) == (4, 5)


def test_center_ish():
    # x in [0.4,0.6) -> col 3, y in [0.5,0.75) -> row 3
    assert field_to_cell(0.5, 0.6) == (3, 3)


def test_boundaries_are_left_inclusive():
    # exactly on a boundary belongs to the higher cell (int truncation)
    assert field_to_cell(0.2, 0.0) == (1, 2)   # x=0.2 -> col index 1 -> col 2
    assert field_to_cell(0.0, 0.25) == (2, 1)  # y=0.25 -> row index 1 -> row 2


@pytest.mark.parametrize("x,y", [(-1.0, -1.0), (5.0, 5.0), (1.0, 1.0)])
def test_out_of_range_clamped(x, y):
    row, col = field_to_cell(x, y)
    assert 1 <= row <= 4
    assert 1 <= col <= 5


def test_cell_to_center_roundtrip():
    for row in range(1, 5):
        for col in range(1, 6):
            x, y = cell_to_center(row, col)
            assert field_to_cell(x, y) == (row, col)


# ---------------------------------------------------------------------------
# debounce / hysteresis
# ---------------------------------------------------------------------------
def test_debounce_requires_persistence():
    d = CellDebouncer(debounce_frames=3, hysteresis=0.0)
    assert d.update(0.1, 0.1) == (1, 1)          # first sample commits
    # jump well into cell (1,2) but it must persist a few frames
    assert d.update(0.30, 0.1) == (1, 1)
    assert d.update(0.30, 0.1) == (1, 1)
    assert d.update(0.30, 0.1) == (1, 2)          # now it switches


def test_hysteresis_holds_near_boundary():
    d = CellDebouncer(debounce_frames=1, hysteresis=0.05)
    d.update(0.1, 0.1)                             # commit (1,1)
    # just barely over the x=0.2 boundary -> within hysteresis margin, hold
    assert d.update(0.205, 0.1) == (1, 1)
    # clearly past the boundary -> allowed to move
    assert d.update(0.30, 0.1) == (1, 2)


# ---------------------------------------------------------------------------
# relay polarity + controller sequencing (with a fake GPIO)
# ---------------------------------------------------------------------------
class FakeGPIO:
    BOARD = "BOARD"
    OUT = "OUT"
    HIGH = 1
    LOW = 0

    def __init__(self):
        self.mode = None
        self.state = {}          # pin -> level
        self.events = []         # ordered log of outputs

    def setmode(self, mode):
        self.mode = mode

    def setwarnings(self, flag):
        pass

    def setup(self, pin, direction, initial=None):
        self.state[pin] = initial

    def output(self, pin, level):
        self.state[pin] = level
        self.events.append((pin, level))

    def cleanup(self):
        self.state.clear()


@pytest.fixture
def controller_with_fake(monkeypatch):
    import tactile.relay_controller as rc

    fake = FakeGPIO()
    monkeypatch.setattr(rc, "GPIO", fake)
    c = rc.RelayController(switch_delay=0.0, active_low=True)
    c.setup()
    fake.events.clear()  # drop the init-to-off writes
    return c, fake, rc


def test_active_low_polarity(controller_with_fake):
    c, fake, _ = controller_with_fake
    pin = ROW_PINS[0]
    c.relay_on(pin)
    assert fake.state[pin] == FakeGPIO.LOW    # active-low: ON == LOW
    c.relay_off(pin)
    assert fake.state[pin] == FakeGPIO.HIGH


def test_active_high_polarity(monkeypatch):
    import tactile.relay_controller as rc
    fake = FakeGPIO()
    monkeypatch.setattr(rc, "GPIO", fake)
    c = rc.RelayController(switch_delay=0.0, active_low=False)
    c.setup()
    pin = ROW_PINS[0]
    c.relay_on(pin)
    assert fake.state[pin] == FakeGPIO.HIGH   # active-high: ON == HIGH


def test_same_cell_does_not_retoggle(controller_with_fake):
    c, fake, _ = controller_with_fake
    c.select_cell(2, 4)
    n_events = len(fake.events)
    c.select_cell(2, 4)   # identical cell
    assert len(fake.events) == n_events        # no new relay activity
    assert c.current_cell == (2, 4)


def test_transition_sequence_off_then_row_then_column(controller_with_fake):
    c, fake, _ = controller_with_fake
    c.select_cell(2, 4)

    row_pin = ROW_PINS[1]     # Row 2 -> pin 13
    col_pin = COLUMN_PINS[3]  # Column 4 -> pin 31
    assert row_pin == 13 and col_pin == 31

    # Everything should have been driven OFF (HIGH for active-low) before the
    # new pair was energized, and the new row+column are the last two ONs.
    on_events = [(p, lvl) for (p, lvl) in fake.events if lvl == FakeGPIO.LOW]
    assert on_events[-2:] == [(row_pin, FakeGPIO.LOW), (col_pin, FakeGPIO.LOW)]
    assert c.current_cell == (2, 4)


def test_invalid_cell_never_activates(controller_with_fake):
    c, fake, _ = controller_with_fake
    for bad in [(0, 1), (5, 1), (1, 0), (1, 6), (-1, -1)]:
        fake.events.clear()
        with pytest.raises(ValueError):
            c.select_cell(*bad)
        assert fake.events == []               # hardware untouched
        assert c.current_cell is None


def test_all_on_energizes_every_relay_line(controller_with_fake):
    c, fake, _ = controller_with_fake
    c.all_on()
    assert set(c._active_pins) == set(ROW_PINS + COLUMN_PINS)
    assert all(fake.state[pin] == FakeGPIO.LOW for pin in ROW_PINS + COLUMN_PINS)
