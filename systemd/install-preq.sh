#!/bin/sh
# Install the Raspberry Pi dependencies and enable both project services.
set -eu

PROJECT_DIR=/opt/raspi-led-controller
VENV_DIR=/opt/led-venv

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo: sudo $0" >&2
    exit 1
fi

if [ ! -f "$PROJECT_DIR/led-212.py" ] \
    || [ ! -f "$PROJECT_DIR/app_logging.py" ] \
    || [ ! -f "$PROJECT_DIR/requirements-rpi.txt" ] \
    || [ ! -f "$PROJECT_DIR/web/serve.py" ]; then
    echo "Project files were not found in $PROJECT_DIR." >&2
    echo "Copy the project to $PROJECT_DIR before running this installer." >&2
    exit 1
fi

echo "Installing system packages..."
apt-get update
apt-get install -y python3-venv python3-pip

echo "Checking for the Raspberry Pi hardware watchdog..."
if modprobe bcm2835_wdt 2>/dev/null && { [ -e /dev/watchdog0 ] || [ -e /dev/watchdog ]; }; then
    install -d /etc/modules-load.d /etc/systemd/system.conf.d
    printf '%s\n' bcm2835_wdt > /etc/modules-load.d/raspi-led-watchdog.conf
    cat > /etc/systemd/system.conf.d/raspi-led-watchdog.conf <<'EOF'
[Manager]
RuntimeWatchdogSec=30s
EOF
    echo "Hardware watchdog enabled; a system-level freeze can trigger a reboot."
    REEXEC_SYSTEMD=1
else
    echo "No bcm2835 hardware watchdog device found; enabling service-level watchdogs only."
fi

echo "Preparing the Python environment..."
if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements-rpi.txt"

echo "Installing systemd services..."
install -m 0644 "$PROJECT_DIR/systemd/led-212.service" /etc/systemd/system/led-212.service
install -m 0644 "$PROJECT_DIR/systemd/led-web.service" /etc/systemd/system/led-web.service
if [ "${REEXEC_SYSTEMD:-0}" -eq 1 ]; then
    systemctl daemon-reexec
fi
systemctl daemon-reload

echo "Enabling and starting the controller and web panel..."
systemctl enable led-212.service led-web.service
systemctl restart led-212.service
systemctl restart led-web.service

echo "Service status:"
systemctl --no-pager --full status led-212.service led-web.service
