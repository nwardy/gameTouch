#!/usr/bin/env python3
"""
Standalone relay hardware debugging tool.

This file's ONLY job is to exercise the physical relays. It does not need the
computer-vision system, OpenCV, or any trajectory. Run it directly on the
Jetson:

    sudo python3 tests/test_relays.py            # sequential auto-test
    sudo python3 tests/test_relays.py --interactive

It always turns every other relay OFF before energizing the next one, and it
always cleans up (relays OFF) on exit, including Ctrl+C.
"""

import os
import sys
import time

# Allow running as a plain script from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tactile.relay_config import ROW_PINS, COLUMN_PINS
from tactile.relay_controller import RelayController

TEST_DURATION = 1.0  # seconds each relay stays on during the auto-test

# (label, physical pin) for all 9 outputs, in test order.
OUTPUTS = (
    [(f"Row {i + 1}", pin) for i, pin in enumerate(ROW_PINS)]
    + [(f"Column {i + 1}", pin) for i, pin in enumerate(COLUMN_PINS)]
)


def print_header():
    print("RELAY TEST")
    print("========================")
    print()
    for i, pin in enumerate(ROW_PINS):
        print(f"Row {i + 1}     Pin {pin}")
    print()
    for i, pin in enumerate(COLUMN_PINS):
        print(f"Column {i + 1}  Pin {pin}")
    print()


def auto_test(controller, duration=TEST_DURATION):
    print("Sequentially testing every relay...\n")
    for label, pin in OUTPUTS:
        controller.all_off()  # ensure every other relay is OFF first
        print(f"Testing {label} - Pin {pin}")
        controller.relay_on(pin)
        print("ON")
        time.sleep(duration)
        controller.relay_off(pin)
        print("OFF\n")
    controller.all_off()


def _activate_single(controller, label, pin):
    controller.all_off()
    controller.relay_on(pin)
    print(f"\nActivating:\n\n{label}\nPhysical Pin: {pin}\n")


def _activate_cell(controller, row, column):
    controller.all_off()
    row_pin = ROW_PINS[row - 1]
    col_pin = COLUMN_PINS[column - 1]
    controller.relay_on(row_pin)
    controller.relay_on(col_pin)
    print(
        f"\nActivating:\n\n"
        f"Row {row}\nPhysical Pin: {row_pin}\n\n"
        f"Column {column}\nPhysical Pin: {col_pin}\n"
    )


def _print_interactive_help():
    print(
        "Commands:\n"
        "  r1..r4     test a single row\n"
        "  c1..c5     test a single column\n"
        "  2,3        activate Row 2 + Column 3\n"
        "  off        all relays off\n"
        "  test       auto-cycle through all 9 outputs\n"
        "  h          show this help\n"
        "  q          all off, cleanup, quit\n"
    )


def interactive(controller):
    _print_interactive_help()
    while True:
        try:
            cmd = input("relay> ").strip().lower()
        except EOFError:
            break
        if not cmd:
            continue

        if cmd == "q":
            break
        elif cmd in ("h", "help", "?"):
            _print_interactive_help()
        elif cmd == "off":
            controller.all_off()
            print("all off")
        elif cmd == "test":
            auto_test(controller)
        elif cmd.startswith("r") and cmd[1:].isdigit():
            n = int(cmd[1:])
            if 1 <= n <= len(ROW_PINS):
                _activate_single(controller, f"Row {n}", ROW_PINS[n - 1])
            else:
                print(f"row must be 1..{len(ROW_PINS)}")
        elif cmd.startswith("c") and cmd[1:].isdigit():
            n = int(cmd[1:])
            if 1 <= n <= len(COLUMN_PINS):
                _activate_single(controller, f"Column {n}", COLUMN_PINS[n - 1])
            else:
                print(f"column must be 1..{len(COLUMN_PINS)}")
        elif "," in cmd:
            try:
                r, c = (int(p) for p in cmd.split(","))
            except ValueError:
                print("format: row,column  e.g. 2,3")
                continue
            if 1 <= r <= len(ROW_PINS) and 1 <= c <= len(COLUMN_PINS):
                _activate_cell(controller, r, c)
            else:
                print(f"row 1..{len(ROW_PINS)}, column 1..{len(COLUMN_PINS)}")
        else:
            print("unknown command (h for help)")


def main():
    interactive_mode = "--interactive" in sys.argv or "-i" in sys.argv
    print_header()

    controller = RelayController()
    controller.setup()
    try:
        if interactive_mode:
            interactive(controller)
        else:
            auto_test(controller)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        controller.cleanup()
        print("relays off, GPIO cleaned up")


if __name__ == "__main__":
    main()
