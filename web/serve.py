#!/usr/bin/env python3
"""Minimal server that serves only the static web page files."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import logging
import os
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WEB_DIR = Path(__file__).resolve().parent
ALLOWED_FILES = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/app.js": "app.js"}
sys.path.insert(0, str(WEB_DIR.parent))
from app_logging import configure_app_logging

configure_app_logging("led-web")


def systemd_notify(message):
    """Send a notification to systemd when running as a managed service."""
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notify_socket:
            notify_socket.sendto(message.encode("utf-8"), address)
    except OSError as error:
        logging.warning("Nie udało się powiadomić systemd: %s", error)


class WatchdogHTTPServer(ThreadingHTTPServer):
    """Send watchdog heartbeats from the server's request loop."""

    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        try:
            watchdog_usec = int(os.environ.get("WATCHDOG_USEC", "0"))
        except ValueError:
            watchdog_usec = 0
        self.watchdog_interval = max(1.0, watchdog_usec / 3_000_000) if watchdog_usec else None
        self.last_watchdog = time.monotonic()

    def service_actions(self):
        if self.watchdog_interval is None:
            return
        now = time.monotonic()
        if now - self.last_watchdog >= self.watchdog_interval:
            systemd_notify("WATCHDOG=1")
            self.last_watchdog = now

    def handle_error(self, request, client_address):
        logging.exception("Web request failed for %s", client_address[0])


class PageHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        filename = ALLOWED_FILES.get(path.split("?", 1)[0])
        return str(WEB_DIR / filename) if filename else str(WEB_DIR / "__not_found__")

    def log_message(self, format_string, *args):
        if self.path.startswith("/api/status"):
            return
        logging.info("%s - %s", self.address_string(), format_string % args)

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
        elif self.path == "/api/restart-ssh":
            self.restart_ssh()
        else:
            self.send_error(404)

    def restart_ssh(self):
        """Restart only the SSH systemd unit through the narrowly scoped sudo rule."""
        try:
            result = subprocess.run(
                ["/usr/bin/sudo", "-n", "/usr/bin/systemctl", "restart", "ssh.service"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            logging.error("Nie udało się zrestartować ssh.service: %s", error)
            self.send_json(503, {"error": "Nie udało się zrestartować usługi SSH."})
            return

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            logging.error("Restart ssh.service nie powiódł się: %s", detail)
            message = "Restart SSH nie powiódł się."
            if detail:
                message += " " + detail[:300]
            self.send_json(503, {"error": message})
            return

        logging.info("Zrestartowano ssh.service z panelu webowego.")
        self.send_json(200, {"message": "Usługa SSH została zrestartowana."})

    def send_json(self, status, data):
        response_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(response_body)


if len(sys.argv) != 3:
    raise SystemExit("Użycie: serve.py HOST PORT")

os.chdir(WEB_DIR)
server = WatchdogHTTPServer((sys.argv[1], int(sys.argv[2])), PageHandler)
logging.info("Serwer statycznej strony działa na %s:%s", sys.argv[1], sys.argv[2])
systemd_notify("READY=1\nSTATUS=Web panel ready")
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    systemd_notify("STOPPING=1")
    server.server_close()
