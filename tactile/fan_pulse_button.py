"""Optional momentary-button input for an on-demand fan-pulse request."""

from tactile.relay_config import ALL_RELAY_PINS


class FanPulseButton:
    """Listen for a button-to-ground press using Jetson BOARD pin numbering."""

    def __init__(self, pin, on_press):
        if pin in ALL_RELAY_PINS:
            raise ValueError(f"fan button pin {pin} conflicts with a relay output")
        self.pin = pin
        self.on_press = on_press
        self._gpio = None

    def start(self):
        try:
            import Jetson.GPIO as gpio
        except ImportError as exc:
            raise RuntimeError("FanPulseButton requires Jetson.GPIO on the Jetson.") from exc
        self._gpio = gpio
        gpio.setmode(gpio.BOARD)
        gpio.setup(self.pin, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.add_event_detect(self.pin, gpio.FALLING, callback=self._pressed, bouncetime=250)

    def _pressed(self, _channel):
        self.on_press()

    def cleanup(self):
        if self._gpio is not None:
            self._gpio.remove_event_detect(self.pin)
