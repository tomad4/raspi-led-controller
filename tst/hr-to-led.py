import asyncio
import board
import neopixel
from bleak import BleakClient, BleakScanner
import signal
import sys
import time

# --- KONFIGURACJA ---
MAC_ADDRESS = "E0:48:24:B5:48:92"
LED_COUNT = 239
BRIGHTNESS = 0.6
PIN = board.D18

# --- STREFY TĘTNA (kolor RGB) ---
ZONES = [
    (0, 80, (255, 255, 255)),    # bialy
    (81, 100, (0, 0, 255)),      # niebieski
    (101, 120, (0, 255, 0)),     # zielony
    (121, 150, (255, 255, 0)),   # żółty
    (151, 180, (255, 0, 0)),     # czerwony
    (181, 300, (255, 0, 0))      # migająca czerwien
]

HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
HR_CHARACTERISTIC = "00002a37-0000-1000-8000-00805f9b34fb"

pixels = neopixel.NeoPixel(PIN, LED_COUNT, brightness=BRIGHTNESS, auto_write=False, pixel_order=neopixel.GRB)

# --- Obsługa zamknięcia ---
def shutdown(signum, frame):
    pixels.fill((0, 0, 0))
    pixels.show()
    sys.exit(0)
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# --- Znajdź odpowiedni kolor dla danego tętna ---
def get_color(hr):
    for (low, high, color) in ZONES:
        if low <= hr <= high:
            return color
    return (0, 0, 0)

# --- Fade (między poprzednim kolorem a nowym) ---
def fade_to_color(current, target, steps=10, delay=0.05):
    for step in range(1, steps + 1):
        intermediate = tuple([
            int(current[i] + (target[i] - current[i]) * step / steps) for i in range(3)
        ])
        pixels.fill(intermediate)
        pixels.show()
        time.sleep(delay)

# --- Główny loop ---
async def run():
    print("דרבה: łączę z zegarkiem...")
    client = BleakClient(MAC_ADDRESS)
    await client.connect()
    print("Połączono z zegarkiem!")

    current_color = (0, 0, 0)
    blink_state = False
    last_zone = -1

    def handle_hr(_, data):
        nonlocal current_color, blink_state, last_zone
        hr = data[1]
        color = get_color(hr)
        zone = next(i for i, (low, high, _) in enumerate(ZONES) if low <= hr <= high)

        if zone != last_zone:
            fade_to_color(current_color, color)
            current_color = color
            last_zone = zone
        elif zone == 5:  # miganie
            blink_state = not blink_state
            pixels.fill(color if blink_state else (0, 0, 0))
            pixels.show()

    await client.start_notify(HR_CHARACTERISTIC, handle_hr)
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await client.stop_notify(HR_CHARACTERISTIC)
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
