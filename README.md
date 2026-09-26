# Tactile Sports Field for Visually Impaired Fans

Takes prerecorded American-football video, determines the ball's path, maps it
onto a **4×5 tactile field**, and drives a matching grid of vibration motors
through relay hardware so a visually impaired person can *feel* where the ball is.

This is a lightweight hackathon prototype. Priorities, in order: get prerecorded
video working reliably → extract the ball path → map to the 4×5 field →
synchronize with playback → deploy to Jetson → connect real relays → (later)
live processing. Efficiency and low latency come first; nothing here is
over-engineered.

---

## The 4×5 grid concept

The physical board has 20 vibration motors in 4 rows × 5 columns. Each motor is
one region of the field. A single **active cell** (one row + one column) follows
the ball. Because the ball stays in a large region for a while, we do **not**
need fast switching — this is not LED multiplexing.

```
            COLUMN
         1   2   3   4   5
ROW 1    ●   ●   ●   ●   ●
ROW 2    ●   ●   ●   ●   ●
ROW 3    ●   ●   ●   ●   ●
ROW 4    ●   ●   ●   ●   ●
```

Normalized field coordinates drive everything:

```
x = 0.0 left edge     x = 1.0 right edge
y = 0.0 top sideline  y = 1.0 bottom sideline
```

`field_to_cell(x, y)` → `(row, column)` (1-based). `cell_to_center(row, column)`
→ normalized center (for visualization).

---

## Architecture (loosely coupled)

Everything downstream depends only on one abstraction:

```
position_source.get_position(timestamp) -> (x, y)  # normalized, or None
```

The source can be a saved trajectory now (`PrerecordedSource`) and live
detection later — nothing else changes. The real-time loop is deliberately tiny:

```python
while playing:
    t       = current_timestamp()
    x, y    = position_source.get_position(t)   # where's the ball?
    row, col = field_to_cell(x, y)              # which of 20 regions?
    tactile_output.set_cell(row, col)           # feel it
    draw_debug(...)
```

Tactile output is also abstracted (`TactileOutput`): `MockTactileOutput` on the
Mac, `JetsonRelayTactileOutput` on the Jetson. Swap via `--hardware` /
`--mock-hardware` — no vision code touches GPIO.

---

## MacBook development

No Jetson or relay hardware required. `Jetson.GPIO` is imported lazily and only
on real hardware, so the whole vision pipeline runs on macOS.

```bash
pip install -r requirements.txt

# Play a clip with the console mock output + on-screen debug overlay.
# First run will prompt you to click the 4 field corners (calibration),
# then drag a box on the ball (tracking) — both are saved for reuse.
python3 main.py --video example.mp4 --name game1 --mock-hardware
```

Try it immediately with the bundled sample trajectory (no video tracking):

```bash
python3 main.py --video example.mp4 --trajectory data/trajectories/sample.json --mock-hardware
```

### Calibration

Convert video pixels → field coordinates with a one-time perspective transform.

```bash
python3 main.py --video example.mp4 --calibrate --name game1
# click corners in order: TOP-LEFT, TOP-RIGHT, BOTTOM-RIGHT, BOTTOM-LEFT
```

Saved to `data/calibration/<name>.json` and reused automatically.

### Trajectory generation

```bash
python3 main.py --video example.mp4 --track --name game1
# drag a box around the ball on the first frame; the tracker takes over.
```

Saved to `data/trajectories/<name>.json` in the format:

```json
[{"time": 0.00, "x": 0.22, "y": 0.61},
 {"time": 0.10, "x": 0.24, "y": 0.60}]
```

The trajectory is generated **once, offline**, then replayed — the video is not
re-analyzed every playback.

### Unit tests

```bash
python3 -m pytest tests/test_mapping.py
```

Covers coordinate→grid, boundaries, invalid values, relay polarity, no-retoggle
on unchanged cell, and the OFF→delay→row→column transition sequence — all
without hardware.

---

## Physical GPIO / relay mapping (Jetson Orin Nano)

40-pin header, **BOARD** numbering (`GPIO.setmode(GPIO.BOARD)`).
9 channels = 4 rows + 5 columns. Relay modules already contain their driver
circuitry — no extra transistors.

| Logical  | Jetson pin | Board input       |
|----------|-----------|-------------------|
| Row 1    | 7         | Keyes IN1         |
| Row 2    | 13        | Keyes IN2         |
| Row 3    | 15        | Keyes IN3         |
| Row 4    | 16        | Keyes IN4         |
| Column 1 | 18        | Keyes IN5         |
| Column 2 | 22        | Keyes IN6         |
| Column 3 | 29        | Keyes IN7         |
| Column 4 | 31        | Keyes IN8         |
| Column 5 | 32        | single-relay IN   |

Pin 6 is ground where appropriate. All pins live in
`tactile/relay_config.py` — the one place to edit if wiring changes.

### Active-low setting

The Keyes/Funduino board is typically **active-low** (drive LOW to energize).
This is a single constant:

```python
RELAY_ACTIVE_LOW = True   # tactile/relay_config.py
```

`relay_on()`/`relay_off()` translate logical on/off into the right physical
level, so no HIGH/LOW assumptions leak into the rest of the code. Flip the one
constant if your board behaves the opposite way.

`select_cell(row, column)` turns off the previous relays, waits
`RELAY_SWITCH_DELAY` (~30 ms), then activates the new row + column. If the cell
hasn't changed it does nothing — no needless mechanical wear.

---

## Hardware debugging

```bash
# Sequentially test all 9 relays (1s each, others OFF):
sudo python3 tests/test_relays.py

# Interactive: r1..r4, c1..c5, "2,3", off, test, q
sudo python3 tests/test_relays.py --interactive

# Cycle every logical cell (1,1)..(4,5); touch the board to verify mapping:
sudo python3 tests/test_grid.py
```

Both are standalone — they need none of the vision system. Every GPIO script
turns relays **off** and calls `GPIO.cleanup()` on exit, including Ctrl+C.

---

## Jetson production mode

```bash
bash scripts/deploy.sh          # installs deps, sets GPIO permissions
sudo python3 main.py --video example.mp4 --name game1 --hardware
```

See `scripts/deploy.sh` for Python version, pip packages, OpenCV, Jetson.GPIO,
and GPIO permission details.

### Swapping mock ↔ Jetson hardware

`main.py` chooses the sink by flag (dependency injection):

```python
output = JetsonRelayTactileOutput() if hardware_mode else MockTactileOutput()
```

That is the only line that differs between laptop and robot.

---

## Performance notes

- Downscale for tracking: `PROCESS_WIDTH = 640` (coordinates scaled back
  before the homography, so accuracy is preserved).
- Skip frames: `PROCESS_EVERY_N_FRAMES = 2`; gaps interpolate on playback.
- We only need which of 20 large regions holds the ball — don't solve a harder
  CV problem than that.
- Smoothing (EMA) + hysteresis + debounce prevent the tactile cell from
  chattering near boundaries, which also protects the mechanical relays.
- Logging prints only when the active cell changes (`t=... field=... cell=...`),
  not every frame.

---

## Project layout

```
main.py                 entry point / CLI
config.py               grid, performance, smoothing, debug settings
video/                  video_loader.py, playback.py (sync loop + overlay)
tracking/               position_source.py (abstraction),
                        prerecorded_source.py, ball_tracker.py
calibration/            field_calibration.py (click corners), homography.py
tactile/                grid_mapper.py, tactile_output.py, mock_output.py,
                        relay_config.py, relay_controller.py
tests/                  test_relays.py, test_grid.py (hardware),
                        test_mapping.py (pure unit tests)
data/                   trajectories/, calibration/
scripts/deploy.sh
```
