"""Test tętna z jednego zegarka Garmin Forerunner na dwóch diodach NeoPixel."""

import asyncio

import board
import neopixel
from bleak import BleakClient, BleakScanner


# Raspberry Pi Zero 2 W, GPIO18, dwie diody NeoPixel.
NUM_PIXELS = 2
PIXEL_PIN = board.D18
BRIGHTNESS = 0.3

# UUID z ble-finder.py był identyfikatorem lokalnym Maca.
# Na Raspberry Pi zegarek jest wybierany po nazwie BLE.
FORERUNNER_NAME = "Forerunner"

HEART_RATE_CHARACTERISTIC = "00002a37-0000-1000-8000-00805f9b34fb"
SCAN_TIMEOUT_SECONDS = 10
RETRY_DELAY_SECONDS = 3

# Każde 10 BPM ma osobny kolor. Obie diody pokazują ten sam kolor.
# Wartości są dolną granicą zakresu: np. 80 oznacza 80–89 BPM.
HR_COLORS = {
    0: (40, 40, 40),       # poniżej 60: biały
    60: (0, 0, 255),       # 60–69: niebieski
    70: (0, 128, 255),     # 70–79: błękitny
    80: (0, 255, 180),     # 80–89: turkusowy
    90: (0, 200, 0),       # 90–99: zielony
    100: (128, 255, 0),    # 100–109: jasnozielony
    110: (255, 255, 0),    # 110–119: żółty
    120: (255, 180, 0),    # 120–129: złoty
    130: (255, 100, 0),    # 130–139: pomarańczowy
    140: (255, 0, 0),      # 140–149: czerwony
    150: (255, 0, 100),    # 150–159: różowoczerwony
    160: (180, 0, 255),    # 160–169: fioletowy
    170: (100, 0, 255),    # 170–179: ciemnofioletowy
    180: (255, 255, 255),  # 180+: biały
}

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    NUM_PIXELS,
    brightness=BRIGHTNESS,
    auto_write=False,
)


def color_for_heart_rate(hr):
    """Zwróć kolor przypisany do przedziału dziesięciu BPM."""
    lower_bound = (hr // 10) * 10
    if lower_bound < 60:
        lower_bound = 0
    lower_bound = min(lower_bound, 180)
    return HR_COLORS[lower_bound]


def show_heart_rate(data, previous_band):
    """Odczytaj standardową charakterystykę HR i zmień kolor przy nowym progu."""
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

    print(f"Tętno: {hr} BPM | zakres: {band if band else '<60'}–{band + 9 if band else 59} BPM")
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
