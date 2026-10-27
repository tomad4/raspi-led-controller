#!/bin/sh
# Install the Raspberry Pi dependencies and enable both project services.
set -eu

PROJECT_DIR=/opt/raspi-led-controller
VENV_DIR=/opt/led-venv

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo: sudo $0" >&2
    exit 1
fi

if [ ! -f "$PROJECT_DIR/led-212.py" ] || [ ! -f "$PROJECT_DIR/requirements-rpi.txt" ]; then
    echo "Project files were not found in $PROJECT_DIR." >&2
    echo "Copy the project to $PROJECT_DIR before running this installer." >&2
    exit 1
fi

echo "Installing system packages..."
apt-get update
apt-get install -y python3-venv python3-pip

echo "Preparing the Python environment..."
if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements-rpi.txt"

echo "Installing systemd services..."
install -m 0644 "$PROJECT_DIR/systemd/led-212.service" /etc/systemd/system/led-212.service
install -m 0644 "$PROJECT_DIR/systemd/led-web.service" /etc/systemd/system/led-web.service
systemctl daemon-reload

echo "Enabling and starting the controller and web panel..."
systemctl enable led-212.service led-web.service
systemctl restart led-212.service
systemctl restart led-web.service

echo "Service status:"
systemctl --no-pager --full status led-212.service led-web.service
