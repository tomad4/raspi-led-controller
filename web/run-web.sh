#!/bin/sh
# Buduje frontend tylko wtedy, gdy brak gotowego dist/, a następnie serwuje go
# lekkim serwerem HTTP z biblioteki standardowej Pythona.
set -eu

WEB_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WEB_HOST=${WEB_HOST:-0.0.0.0}
WEB_PORT=${WEB_PORT:-8000}

if ! command -v python3 >/dev/null 2>&1; then
    echo "Błąd: wymagany jest python3." >&2
    exit 1
fi

if [ ! -f "$WEB_DIR/dist/index.html" ]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "Błąd: do pierwszego builda potrzebne są Node.js i npm." >&2
        echo "Zainstaluj je, uruchom npm install w katalogu web/, a potem ponów skrypt." >&2
        exit 1
    fi

    if [ ! -x "$WEB_DIR/node_modules/.bin/vite" ] || \
       [ ! -d "$WEB_DIR/node_modules/@vitejs/plugin-react" ]; then
        echo "Instaluję zależności frontendu..."
        cd "$WEB_DIR"
        if [ -f package-lock.json ]; then
            npm ci --no-audit --no-fund
        else
            npm install --no-audit --no-fund
        fi
    fi

    echo "Buduję frontend (limit sterty Node.js: 256 MB)..."
    cd "$WEB_DIR"
    NODE_OPTIONS=${NODE_OPTIONS:---max-old-space-size=256} npm run build
fi

echo "Frontend dostępny na http://<adres-Raspberry-Pi>:$WEB_PORT"
echo "Zatrzymaj serwer przez Ctrl+C."
exec python3 -m http.server "$WEB_PORT" --bind "$WEB_HOST" --directory "$WEB_DIR/dist"
