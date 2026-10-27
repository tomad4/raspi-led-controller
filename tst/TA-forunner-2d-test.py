"""Test heart-rate readings from a Garmin Forerunner on two NeoPixel LEDs."""

import asyncio

import board
import neopixel
from bleak import BleakClient, BleakScanner


# Raspberry Pi Zero 2 W, GPIO18, two NeoPixel LEDs.
NUM_PIXELS = 2
PIXEL_PIN = board.D18
BRIGHTNESS = 0.3

# The UUID reported by ble-finder.py was a local Mac identifier.
# On Raspberry Pi, the watch is selected by its BLE name.
FORERUNNER_NAME = "Forerunner"

HEART_RATE_CHARACTERISTIC = "00002a37-0000-1000-8000-00805f9b34fb"
SCAN_TIMEOUT_SECONDS = 10
RETRY_DELAY_SECONDS = 3

# Each 10 BPM interval has its own color. Both LEDs show the same color.
# Values are lower bounds: for example, 80 represents 80–89 BPM.
HR_COLORS = {
    0: (40, 40, 40),       # below 60: white
    60: (0, 0, 255),       # 60–69: blue
    70: (0, 128, 255),     # 70–79: light blue
    80: (0, 255, 180),     # 80–89: turquoise
    90: (0, 200, 0),       # 90–99: green
    100: (128, 255, 0),    # 100–109: light green
    110: (255, 255, 0),    # 110–119: yellow
    120: (255, 180, 0),    # 120–129: gold
    130: (255, 100, 0),    # 130–139: orange
    140: (255, 0, 0),      # 140–149: red
    150: (255, 0, 100),    # 150–159: pink-red
    160: (180, 0, 255),    # 160–169: purple
    170: (100, 0, 255),    # 170–179: dark purple
    180: (255, 255, 255),  # 180+: white
}

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    NUM_PIXELS,
    brightness=BRIGHTNESS,
    auto_write=False,
)


def color_for_heart_rate(hr):
    """Return the color assigned to a ten-BPM interval."""
    lower_bound = (hr // 10) * 10
    if lower_bound < 60:
        lower_bound = 0
    lower_bound = min(lower_bound, 180)
    return HR_COLORS[lower_bound]


def show_heart_rate(data, previous_band):
    """Read the standard HR characteristic and change color when the band changes."""
    if len(data) < 2:
        print("Odebrano niepełny pomiar tętna.")
        return previous_band

    flags = data[0]
    if flags & 0x01:
        if len(data) < 3:
            print("Odebrano niepełny 16-bitowy pomiar tętna.")
            return previous_band
        hr = int.from_bytes(data[1:3], byteorder="little")
    else:
        hr = data[1]

    if not 30 <= hr <= 240:
        print(f"Pomijam nieprawidłowe tętno: {hr} BPM")
        return previous_band

    band = min((hr // 10) * 10, 180)
    if band < 60:
        band = 0

    if band == 0:
        range_label = "poniżej 60"
    elif band == 180:
        range_label = "180 lub więcej"
    else:
        range_label = f"{band}–{band + 9}"

    print(f"Tętno: {hr} BPM | zakres: {range_label} BPM")
    if band != previous_band:
        pixels.fill(color_for_heart_rate(hr))
        pixels.show()
        print(f"Kolor diod zmieniony dla progu {band} BPM.")

    return band


async def find_forerunner():
    print(f"Szukam zegarka Garmin {FORERUNNER_NAME}...")
    discovered = await BleakScanner.discover(
        timeout=SCAN_TIMEOUT_SECONDS,
        return_adv=True,
    )

    for device, advertisement in discovered.values():
        names = {device.name, advertisement.local_name}
        names.discard(None)
        if any(FORERUNNER_NAME.casefold() in name.casefold() for name in names):
            print(f"Znaleziono {device.name or FORERUNNER_NAME}: {device.address}")
            return device

    return None


async def run_forerunner(device):
    last_band = None

    async with BleakClient(device) as client:
        print("Połączono. Oczekuję na pomiary tętna; Ctrl+C kończy test.")

        def on_heart_rate(_sender, data):
            nonlocal last_band
            last_band = show_heart_rate(data, last_band)

        await client.start_notify(HEART_RATE_CHARACTERISTIC, on_heart_rate)
        while client.is_connected:
            await asyncio.sleep(1)

    pixels.fill((0, 0, 0))
    pixels.show()


async def main():
    while True:
        device = await find_forerunner()
        if device is None:
            print("Nie znaleziono Forerunnera. Ponawiam za chwilę.")
            await asyncio.sleep(RETRY_DELAY_SECONDS)
            continue

        try:
            await run_forerunner(device)
        except Exception as error:
            print(f"Połączenie BLE przerwane: {type(error).__name__}: {error}")
            await asyncio.sleep(RETRY_DELAY_SECONDS)
        finally:
            pixels.fill((0, 0, 0))
            pixels.show()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Kończę test.")
    finally:
        pixels.fill((0, 0, 0))
        pixels.show()
        pixels.deinit()
