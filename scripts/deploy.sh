#!/usr/bin/env bash
#
# Jetson Orin Nano deployment helper.
# Target: NVIDIA Jetson Orin Nano, Ubuntu Linux.
#
# This is intentionally simple. Read it before running; it only installs
# lightweight dependencies and sets up GPIO permissions.

set -e

echo "== Tactile field: Jetson deployment =="

# 1. Python version --------------------------------------------------------
# Jetson Orin Nano ships with Python 3.8+. Anything >= 3.8 is fine.
python3 --version

# 2. Required pip packages -------------------------------------------------
# numpy is needed by the vision pipeline. opencv is installed separately below.
python3 -m pip install --upgrade pip
python3 -m pip install numpy

# 3. OpenCV ----------------------------------------------------------------
# Prefer the JetPack-provided OpenCV (often CUDA-enabled). If `import cv2`
# already works, skip this. Otherwise install the contrib build for trackers:
python3 - <<'PY' || python3 -m pip install opencv-contrib-python
import cv2  # noqa
print("OpenCV already present:", cv2.__version__)
PY

# 4. Jetson.GPIO -----------------------------------------------------------
sudo python3 -m pip install Jetson.GPIO

# 5. GPIO permissions ------------------------------------------------------
# Allow the current user to access the GPIO without sudo (optional; the test
# and main commands below use sudo anyway).
sudo groupadd -f gpio
sudo usermod -aG gpio "$USER"
# udev rules so /dev/gpiochip* is group-accessible:
if [ -f /opt/nvidia/jetson-gpio/etc/99-gpio.rules ]; then
  sudo cp /opt/nvidia/jetson-gpio/etc/99-gpio.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger
fi
echo "NOTE: log out/in (or reboot) for gpio group membership to take effect."

# 6-8. How to run ----------------------------------------------------------
cat <<'EOF'

Deployment done. Usage:

  6. Relay hardware test:
       sudo python3 tests/test_relays.py
       sudo python3 tests/test_relays.py --interactive

  7. Logical grid test (touch each motor to verify mapping):
       sudo python3 tests/test_grid.py

  8. Run the main application (real hardware):
       sudo python3 main.py --video input.mp4 --name game1 --hardware

  (MacBook development, no hardware:)
       python3 main.py --video input.mp4 --name game1 --mock-hardware
EOF
