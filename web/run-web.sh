#!/bin/sh
# Serwuje lekki, statyczny panel bez Node.js, npm ani procesu budowania.
set -eu

WEB_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WEB_HOST=${WEB_HOST:-0.0.0.0}
WEB_PORT=${WEB_PORT:-8000}

if ! command -v python3 >/dev/null 2>&1; then
    echo "Błąd: wymagany jest python3." >&2
    exit 1
fi

echo "Statyczny panel dostępny na http://<adres-Raspberry-Pi>:$WEB_PORT"
echo "Zatrzymaj serwer przez Ctrl+C."
exec python3 "$WEB_DIR/serve.py" "$WEB_HOST" "$WEB_PORT"
