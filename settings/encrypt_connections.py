#!/usr/bin/env python3
"""Encrypt settings/connections.json with a Fernet key stored outside the project."""

import argparse
import os
from pathlib import Path

from cryptography.fernet import Fernet


SETTINGS_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-key", metavar="PATH", help="Create a key file at PATH (keep it outside the project).")
    parser.add_argument("--remove-plaintext", action="store_true", help="Remove connections.json after encryption.")
    args = parser.parse_args()

    key_file = Path(args.generate_key) if args.generate_key else None
    if key_file:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(Fernet.generate_key())
        os.chmod(key_file, 0o600)
        os.environ["LED_CONNECTIONS_KEY_FILE"] = str(key_file)

    key = os.environ.get("LED_CONNECTIONS_KEY")
    key_path = os.environ.get("LED_CONNECTIONS_KEY_FILE")
    if not key and key_path:
        key = Path(key_path).read_text(encoding="ascii").strip()
    if not key:
        parser.error("Set LED_CONNECTIONS_KEY_FILE or use --generate-key PATH.")

    source = SETTINGS_DIR / "connections.json"
    if not source.is_file():
        parser.error("Create settings/connections.json from connections.example.json first.")
    encrypted = Fernet(key.encode("ascii")).encrypt(source.read_bytes())
    (SETTINGS_DIR / "connections.enc").write_bytes(encrypted)
    if args.remove_plaintext:
        source.unlink()
    print("Encrypted BLE settings written to settings/connections.enc.")
    print("Keep the key file outside the project and configure LED_CONNECTIONS_KEY_FILE for the service.")


if __name__ == "__main__":
    main()
