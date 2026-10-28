"""Load strip geometry and optional encrypted BLE connection settings."""

import json
import os
from pathlib import Path


SETTINGS_DIR = Path(__file__).resolve().parent


def _load_json(path):
    with path.open("r", encoding="utf-8") as settings_file:
        return json.load(settings_file)


def load_strip_settings():
    settings = _load_json(SETTINGS_DIR / "strip.json")
    pixel_count = int(settings["pixel_count"])
    start, end = (int(value) for value in settings["active_range"])
    if pixel_count < 1 or not 1 <= start <= end <= pixel_count:
        raise ValueError("Invalid LED pixel_count or active_range in settings/strip.json")
    for name, segment in settings["segments"].items():
        if segment and (len(segment) != 2 or not 1 <= int(segment[0]) <= int(segment[1]) <= pixel_count):
            raise ValueError(f"Invalid LED segment {name!r} in settings/strip.json")
    return settings


def load_connection_settings():
    encrypted_path = SETTINGS_DIR / "connections.enc"
    plain_path = SETTINGS_DIR / "connections.json"
    if encrypted_path.exists():
        key = os.environ.get("LED_CONNECTIONS_KEY")
        key_file = os.environ.get("LED_CONNECTIONS_KEY_FILE")
        if not key and key_file:
            key = Path(key_file).read_text(encoding="ascii").strip()
        if not key:
            raise RuntimeError(
                "settings/connections.enc exists, but LED_CONNECTIONS_KEY or "
                "LED_CONNECTIONS_KEY_FILE is not configured."
            )
        try:
            from cryptography.fernet import Fernet, InvalidToken
        except ImportError as error:
            raise RuntimeError("Install the optional 'cryptography' package to read encrypted settings.") from error
        try:
            decrypted = Fernet(key.encode("ascii")).decrypt(encrypted_path.read_bytes())
            return json.loads(decrypted.decode("utf-8"))
        except (ValueError, InvalidToken, json.JSONDecodeError) as error:
            raise RuntimeError("Could not decrypt settings/connections.enc; check the configured key.") from error
    if plain_path.exists():
        return _load_json(plain_path)
    return _load_json(SETTINGS_DIR / "connections.example.json")


STRIP_SETTINGS = load_strip_settings()
CONNECTION_SETTINGS = load_connection_settings()
