"""
Hardware-specific relay configuration for the Jetson Orin Nano.

All physical pin numbers use the 40-pin header with BOARD numbering
(GPIO.setmode(GPIO.BOARD)).

Keep ALL hardware assumptions in this one file so the physical board can be
re-wired or its polarity flipped by editing a single place.
"""

# Physical BOARD pin numbers.
ROW_PINS = [
    7,    # Row 1  -> IN1
    13,   # Row 2  -> IN2
    15,   # Row 3  -> IN3
    16,   # Row 4  -> IN4
]

COLUMN_PINS = [
    18,   # Column 1 -> IN5
    22,   # Column 2 -> IN6
    29,   # Column 3 -> IN7
    31,   # Column 4 -> IN8
    32,   # Column 5 -> single relay IN
]

ALL_RELAY_PINS = ROW_PINS + COLUMN_PINS

# The Keyes/Funduino 8-channel board is typically ACTIVE-LOW:
# driving the pin LOW energizes the relay. Flip this single constant if your
# physical board behaves the opposite way.
RELAY_ACTIVE_LOW = True

# Short settle delay when switching cells. Mechanical relays do not need fast
# switching for this application (~20-50 ms is plenty).
RELAY_SWITCH_DELAY = 0.03
