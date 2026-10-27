#!/usr/bin/env python3
"""Minimal server that serves only the static web page files."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WEB_DIR = Path(__file__).resolve().parent
ALLOWED_FILES = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/app.js": "app.js"}


class PageHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        filename = ALLOWED_FILES.get(path.split("?", 1)[0])
        return str(WEB_DIR / filename) if filename else str(WEB_DIR / "__not_found__")

    def log_message(self, format_string, *args):
        print("[%s] %s" % (self.log_date_time_string(), format_string % args))

    def proxy_api(self, method, path):
        body = None
        if method == "POST":
            length = min(int(self.headers.get("Content-Length", "0")), 2048)
            body = self.rfile.read(length)
        request = Request(
            f"http://127.0.0.1:8765{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=3) as response:
                status, response_body = response.status, response.read(4096)
        except HTTPError as error:
            status, response_body = error.code, error.read(4096)
        except (URLError, TimeoutError, OSError):
            status, response_body = 503, b'{"error":"Sterownik LED jest niedostepny."}'

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self):
        if self.path == "/api/status":
            self.proxy_api("GET", "/status")
        elif self.path in ALLOWED_FILES:
            super().do_GET()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/control":
            self.proxy_api("POST", "/control")
        else:
            self.send_error(404)


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
