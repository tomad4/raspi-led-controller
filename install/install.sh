#!/bin/sh
# Install the project or deploy changed files and restart its services.
set -eu

PROJECT_DIR=/opt/raspi-led-controller
VENV_DIR=/opt/led-venv
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
SOURCE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)
MODE=install

usage() {
    echo "Usage: sudo $0 [-update|--update]" >&2
    echo "  (no flag)  Full install for a new setup" >&2
    echo "  -update    Deploy changed project files and restart services" >&2
}

if [ "$#" -gt 1 ]; then
    usage
    exit 2
fi
if [ "$#" -eq 1 ]; then
    case "$1" in
        -update|--update) MODE=update ;;
        -h|--help) usage; exit 0 ;;
        *) usage; exit 2 ;;
    esac
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo: sudo $0${1:+ $1}" >&2
    exit 1
fi

if [ ! -f "$SOURCE_DIR/led-212.py" ] \
    || [ ! -f "$SOURCE_DIR/app_logging.py" ] \
    || [ ! -f "$SOURCE_DIR/requirements-rpi.txt" ] \
    || [ ! -f "$SOURCE_DIR/web/serve.py" ] \
    || [ ! -f "$SOURCE_DIR/install/led-212.service" ] \
    || [ ! -f "$SOURCE_DIR/install/led-web.service" ]; then
    echo "The project source is incomplete: $SOURCE_DIR" >&2
    exit 1
fi

if [ "$MODE" = update ] && [ ! -d "$PROJECT_DIR" ]; then
    echo "No installation found at $PROJECT_DIR. Run the installer without -update first." >&2
    exit 1
fi

if [ "$MODE" = install ]; then
    echo "Installing system packages..."
    apt-get update
    apt-get install -y python3-venv python3-pip rsync
elif ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required for updates. Run the installer without -update, or install rsync first." >&2
    exit 1
fi

REQUIREMENTS_CHANGED=0
LED_UNIT_CHANGED=1
WEB_UNIT_CHANGED=1
if [ "$MODE" = update ] && [ -d "$PROJECT_DIR" ]; then
    if [ -f "$PROJECT_DIR/requirements-rpi.txt" ] \
        && cmp -s "$SOURCE_DIR/requirements-rpi.txt" "$PROJECT_DIR/requirements-rpi.txt"; then
        REQUIREMENTS_CHANGED=0
    else
        REQUIREMENTS_CHANGED=1
    fi
    if [ -f /etc/systemd/system/led-212.service ] \
        && cmp -s "$SOURCE_DIR/install/led-212.service" /etc/systemd/system/led-212.service; then
        LED_UNIT_CHANGED=0
    fi
    if [ -f /etc/systemd/system/led-web.service ] \
        && cmp -s "$SOURCE_DIR/install/led-web.service" /etc/systemd/system/led-web.service; then
        WEB_UNIT_CHANGED=0
    fi
fi

install -d "$PROJECT_DIR"
if [ "$SOURCE_DIR" != "$PROJECT_DIR" ]; then
    echo "Deploying project files from $SOURCE_DIR to $PROJECT_DIR..."
    rsync -a \
        --exclude='/.git/' \
        --exclude='/.venv/' \
        --exclude='/venv/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        "$SOURCE_DIR/" "$PROJECT_DIR/"
else
    echo "Project source is already in $PROJECT_DIR; skipping file copy."
fi

if [ "$MODE" = install ]; then
    echo "Checking for the Raspberry Pi hardware watchdog..."
    if modprobe bcm2835_wdt 2>/dev/null && { [ -e /dev/watchdog0 ] || [ -e /dev/watchdog ]; }; then
        install -d /etc/modules-load.d /etc/systemd/system.conf.d
        printf '%s\n' bcm2835_wdt > /etc/modules-load.d/raspi-led-watchdog.conf
        cat > /etc/systemd/system.conf.d/raspi-led-watchdog.conf <<'EOF'
[Manager]
RuntimeWatchdogSec=30s
EOF
        echo "Hardware watchdog enabled."
        REEXEC_SYSTEMD=1
    else
        echo "No bcm2835 hardware watchdog device found; service watchdogs remain enabled."
    fi

    echo "Preparing the Python environment..."
    if [ ! -x "$VENV_DIR/bin/python" ]; then
        python3 -m venv --system-site-packages "$VENV_DIR"
    fi
    "$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements-rpi.txt"
else
    if ! systemctl is-active --quiet led-212.service \
        || ! systemctl is-active --quiet led-web.service; then
        echo "One or both project services are not active; update will still deploy and restart them."
    fi
    if [ "$REQUIREMENTS_CHANGED" -eq 1 ]; then
        echo "Python requirements changed; updating the existing virtual environment..."
        if [ ! -x "$VENV_DIR/bin/python" ]; then
            echo "Python environment missing at $VENV_DIR. Run the installer without -update." >&2
            exit 1
        fi
        "$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements-rpi.txt"
    fi
fi

echo "Installing changed systemd service definitions..."
if [ "$MODE" = install ] || [ "$LED_UNIT_CHANGED" -eq 1 ]; then
    install -m 0644 "$PROJECT_DIR/install/led-212.service" /etc/systemd/system/led-212.service
fi
if [ "$MODE" = install ] || [ "$WEB_UNIT_CHANGED" -eq 1 ]; then
    install -m 0644 "$PROJECT_DIR/install/led-web.service" /etc/systemd/system/led-web.service
fi
if [ "${REEXEC_SYSTEMD:-0}" -eq 1 ]; then
    systemctl daemon-reexec
fi
if [ "$MODE" = install ] || [ "$LED_UNIT_CHANGED" -eq 1 ] || [ "$WEB_UNIT_CHANGED" -eq 1 ]; then
    systemctl daemon-reload
fi

echo "Enabling and restarting the controller and web panel..."
systemctl enable led-212.service led-web.service
systemctl restart led-212.service
systemctl restart led-web.service

echo "Service status:"
systemctl --no-pager --full status led-212.service led-web.service
