# Tactile Sports Field for Visually Impaired Fans

Takes prerecorded American-football video, determines the ball's path, maps it
onto a **4×5 tactile field**, and drives a matching grid of vibration motors
through relay hardware so a visually impaired person can *feel* where the ball is.

This is a lightweight hackathon prototype. Priorities, in order: get prerecorded
video working reliably → extract the ball path → map to the 4×5 field →
synchronize with playback → deploy to Jetson → connect real relays → (later)
live processing. Efficiency and low latency come first; nothing here is
over-engineered.

## Presentation control room

For a polished demo, run the local browser control page on the presentation
laptop:

```bash
python3 scripts/make_web_demo_assets.py
python3 demo_server.py
```

Open `http://localhost:8000`. It shows the original game footage and the
precomputed bird's-eye/field-view video side by side. You can replace either
panel with a local video file using the upload controls. Those uploads stay in
the browser tab so the page never silently copies a large video anywhere.
The asset script makes a browser-safe WebM copy of the selected generated MP4;
it does not change the original output used by the Python/Jetson pipeline.

For a browser-only rehearsal, opening `web/index.html` directly also works:
the button plays both local videos together. Run `demo_server.py` only when
you want the button to send the shared start cue to a Jetson.

The Start button creates one shared timestamp after a five-second countdown.
That gives the browser and a Jetson on the local network time to arm;
for this prototype, describe it as a **synchronized replay**, not live video
generation. The displayed field view is generated before the demo.

On the Jetson, copy the same source video and its saved trajectory/calibration,
then leave this client running before the presentation:

```bash
python3 jetson_demo_client.py \
  --server http://PRESENTATION_LAPTOP_IP:8000 \
  --video /path/to/soccer.mp4 --name soccer-fixed-view
```

Use `--mock-hardware` to rehearse the cue without GPIO. The client starts
`main.py --hardware` at the same server-selected timestamp; `main.py` remains
the source of truth for timestamp-to-tactile-cell synchronization.

## Contributor

Current project contributor: **lollipop999**.

## Live fan pulse (optional)

During playback, the optional fan pulse samples a small set of recent public X
posts matching a game query and asks Grok for a short, careful reaction summary.
It runs in a background thread, so a network delay never pauses the tactile
experience. The summary is a sample of online reaction—not a fact about all
fans—and it avoids usernames and repeating harmful content.

Copy `.env.example` to `.env`, then paste your xAI key into its one value. `.env`
is ignored by Git and is loaded only on your own machine; never commit or paste
the actual keys into chat, source files, or screenshots.

```bash
cp .env.example .env
```

Grok's server-side X Search retrieves the public X-post sample, so you do not need an X developer account or X bearer token. It also uses web search for live game context when a reliable score source is available. Use a precise matchup hashtag or team names. While the video window is focused,
press **F** to request one summary. The video and tactile grid keep running
while the request happens in the background. The overlay and terminal show a
live game-context line, a 0–100 fan-intensity score, and an accessible explanation.
Web-derived game context and X-derived fan reaction remain separate; neither is
treated as an official sports-data feed.

### Soccer event patterns

When Grok finds a soccer event in reliable live web context with medium or high
confidence, the board plays a short pattern once, then returns to following the
ball cell. The debug view and terminal name the event and pattern. A
low-confidence event never vibrates the board.

| Event | Board pattern |
| --- | --- |
| Goal | Three full-board blinks |
| Yellow card | Two short taps at the ball cell |
| Red card | Two long full-board alerts |
| Offside | Short then long tap at the ball cell |
| Penalty awarded | One long plus two short taps at the ball cell |
| Corner kick | Four quick taps at the ball cell |
| Substitution | One long then one short tap at the ball cell |
| VAR review | Two slow taps at the ball cell |

On the Jetson, you can connect a normally-open momentary button between an
unused BOARD-numbered GPIO pin and ground, then add `--hardware --fan-button-pin
37` to the command. Pin 37 is only an example: check it does not conflict with
your own wiring before using it. Pressing that button makes the same request as
the **F** key.

### Test Grok and X without video or hardware

Run one live check with the same code path used during playback:

```bash
./.venv/bin/python scripts/test_fan_pulse_live.py --query "#GTvsUGA"
```

It requires only `XAI_API_KEY` in `.env`.
The script prints only the post count and Grok's summary; it never prints either key or saves the posts.

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
# First run will prompt you to click visible field landmarks and enter their
# real yard coordinates (calibration),
# then drag a box on the ball (tracking) — both are saved for reuse.
python3 main.py --video example.mp4 --name game1 --mock-hardware
```

Try it immediately with the bundled sample trajectory (no video tracking):

```bash
python3 main.py --video example.mp4 --trajectory data/trajectories/sample.json --mock-hardware
```

### Calibration

Convert video pixels → a 105 m × 68 m soccer pitch with a one-time perspective
transform. The video does not need to show the four pitch corners.

```bash
python3 main.py --video example.mp4 --calibrate --name game1
# click visible pitch marking; enter x,y metres in the terminal (add 4+ points)
```

Use `--calibrate-only` if the only goal is to save field geometry. Without it,
the program proceeds to the trajectory step after calibration; if no saved
trajectory exists, it opens automatic tracking.

Add `--calibrate-only` when you want to save the mapping now and annotate the
ball path in a separate command.

Use recognizable markings such as touchline/halfway-line intersections, penalty
area corners, and the center-circle/halfway-line intersections. Coordinate
convention: `x=0` and `x=105` are the goal lines; `y=0` is the near touchline
and `y=68` the far touchline.
Saved to `data/calibration/<name>.json` and reused automatically.

### One camera shift in an otherwise fixed clip

If the view makes one small reposition and then stays still, save a second
calibration at the first stable frame after that movement:

```bash
python3 main.py --video soccer.mp4 --name soccer-fixed-view \
  --calibrate-shift --calibrate-only
```

The clip opens paused. Navigate to the first stable **post-shift** frame with
`SPACE` (play/pause), `.`/`,` (one frame), or `l`/`j` (five frames), then press
`ENTER`. Calibrate the landmarks again. The saved calibration automatically
uses the first mapping before that timestamp and the new mapping afterward,
including during manual ball annotation, tracking, and debug playback.

This is designed for discrete shifts/cuts that settle. It is not a substitute
for camera stabilization when the broadcast keeps panning, zooming, or moving.

For slight camera wobble or slow adjustment within either calibrated segment,
the app also follows the clicked landmark pixels (usually white-line
intersections) with optical flow and rebuilds the grid for the current frame.
If fewer than four landmarks can be followed safely, it falls back to the
saved mapping rather than guessing. This is on by default; add `--static-grid`
to disable it while diagnosing a clip.

### Trajectory generation

```bash
python3 main.py --video example.mp4 --track --name game1
# drag a box around the ball on the first frame; the tracker takes over.
```

Saved to `data/trajectories/<name>.json`. Each point preserves normalized
coordinates for the tactile grid and physical field coordinates for analysis:

```json
[{"time": 0.00, "x": 0.22, "y": 0.61,
  "x_meters": 22.0, "y_meters": 32.53,
  "tracking_status": "tracked", "source": "manual_tracker"}]
```

The trajectory is generated **once, offline**, then replayed — the video is not
re-analyzed every playback. If the tracker loses the ball, it pauses on that
frame and asks you to click the ball's center; it reuses the previous box size
and continues. Cancelled/lost spans remain unknown instead of producing a
made-up position.

For white-ball clips, a lightweight guard rejects a tracker target when its
center lies on a player-sized white pixel component. It then searches locally
for a much smaller moving white component; if none is trustworthy, it asks for
a click instead of following a white shirt. The limits live in `config.py` and
are scaled to the video's resolution. This is a practical safety check, not a
replacement for a learned ball detector.

### Manual path for a small or fast ball

When the ball is too small for the OpenCV tracker, annotate a timestamped path
instead of trying to draw one freehand. The video pauses by default: click the
ball, step forward, and click it again. Each point is saved at that video time.
Manual clicks up to one second apart are intentionally interpolated in the
bird's-eye output; automatic-tracker gaps remain limited to 0.25 seconds so a
lost track is never presented as a real ball location.

```bash
python3 main.py --video soccer.mp4 --name soccer-fixed-view \
  --manual-path --mock-hardware \
  --birdseye-output data/outputs/soccer-fixed-view-birdseye.mp4
```

To repair only a missed frame while preserving your existing clicks, add
`--resume-manual-path`.

Controls: `click` saves the ball point; `g` marks the **next** click as a goal;
`SPACE` plays/pauses; `.`/`,` steps one frame; `l`/`j` jumps five frames;
`BACKSPACE` removes a point; `ENTER` saves.

The field calibration describes the grass plane, so a raised net does not
always map beyond the goal line. At the scoring frame, press `g`, then click
the ball in the net. This saves a goal event and places its visualization in
the correct net; annotation continues normally until `ENTER`. At the end of playback and the
bird's-eye MP4, the ball appears in the net; after 0.3 seconds, all 20 tactile
sensors flash three times. On physical hardware this energizes every row and
column relay line, so verify the board is wired as the intended 4×5 matrix
before using the celebration effect with motors attached.

### Bird's-eye MP4 output

After a trajectory exists, render a shareable top-down MP4 of the ball moving
across a marked 105 m by 68 m soccer pitch:

```bash
python3 main.py --video example.mp4 --name game1 --mock-hardware \
  --birdseye-output data/outputs/game1-birdseye.mp4
```

Add `--birdseye-speed 0.25` to export the same path at quarter speed for
inspection.

### Tennis mode

Tennis is a separate 23.77 m × 10.97 m doubles-court profile. For a singles
court use `--sport tennis-singles` (23.77 m × 8.23 m). Use a different name so
soccer and tennis calibrations/paths remain separate:

```bash
python3 main.py --video tennis.mp4 --sport tennis --name tennis-match \
  --calibrate --calibrate-only
python3 main.py --video tennis.mp4 --sport tennis --name tennis-match \
  --manual-path --mock-hardware \
  --birdseye-output data/outputs/tennis-match.mp4
```

For an overhead tennis view, click court corners, service-line intersections,
and the net/sideline intersections during calibration. In manual tennis mode,
press `1` before clicking the ball to mark a point for the near side, or `2`
for the far side. Replay then buzzes that side's court-edge sensor strip.
Point ownership is deliberately manual: ball coordinates alone do not reliably
determine tennis scoring.

For a very fast, tiny tennis ball, use `--track-every-frame` and
`--track-full-resolution`. This is slower to process offline, but preserves
more ball detail than the default efficient soccer settings.

Exports never replace an existing MP4. If `game1-birdseye.mp4` already exists,
the next export is saved as `game1-birdseye-001.mp4`, then `-002.mp4`, and so
on.

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
