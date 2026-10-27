#!/usr/bin/env python3
"""Minimalny serwer udostępniający wyłącznie pliki statycznej strony."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import sys


WEB_DIR = Path(__file__).resolve().parent
ALLOWED_FILES = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/app.js": "app.js"}


class PageHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        filename = ALLOWED_FILES.get(path.split("?", 1)[0])
        return str(WEB_DIR / filename) if filename else str(WEB_DIR / "__not_found__")

    def log_message(self, format_string, *args):
        print("[%s] %s" % (self.log_date_time_string(), format_string % args))


if len(sys.argv) != 3:
    raise SystemExit("Użycie: serve.py HOST PORT")

os.chdir(WEB_DIR)
server = ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), PageHandler)
print(f"Serwer statycznej strony działa na {sys.argv[1]}:{sys.argv[2]}", flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
