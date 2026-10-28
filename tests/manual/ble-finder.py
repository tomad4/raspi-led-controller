#!/usr/bin/env python3
"""Scan for BLE devices for 30 seconds and print their name, address, and RSSI.

On Raspberry Pi, run it in the project's virtual environment:
    /opt/led-venv/bin/python /opt/raspi-led-controller/tests/manual/ble-finder.py

This script does not use GPIO or the main LED application.
"""

import asyncio
import sys
import traceback

from bleak import BleakScanner


SCAN_SECONDS = 30


async def main():
    devices = {}

    def on_device(device, advertisement):
        address = device.address
        name = advertisement.local_name or device.name or "Brak nazwy"
        rssi = advertisement.rssi
        previous = devices.get(address)

        # Store the latest RSSI per address without printing every packet.
        devices[address] = (
            name if previous is None or name != "Brak nazwy" else previous[0],
            rssi,
        )
        if previous is None or (previous[0] == "Brak nazwy" and name != "Brak nazwy"):
            print(f"Nazwa: {name} | Adres: {address} | RSSI: {rssi} dBm", flush=True)

    print(f"Skanuję BLE przez {SCAN_SECONDS} sekund. Ctrl+C kończy skan.", flush=True)
    async with BleakScanner(detection_callback=on_device):
        await asyncio.sleep(SCAN_SECONDS)

    print(f"\nZnaleziono {len(devices)} urządzeń.")
    if not devices:
        print("Nie odebrano żadnych reklam BLE.")
    else:
        print("Ostatnie odebrane wartości RSSI:")
        for address, (name, rssi) in sorted(
            devices.items(), key=lambda item: item[1][1], reverse=True
        ):
            print(f"  {name} | {address} | {rssi} dBm")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Skanowanie przerwane.")
    except Exception:
        print("Nie udało się uruchomić skanowania BLE:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
