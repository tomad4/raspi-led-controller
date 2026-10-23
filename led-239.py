import asyncio
import time
import board
import neopixel
from bleak import BleakScanner, BleakClient
import logging

# === CONFIG ===
NUM_PIXELS = 210
PIXEL_PIN = board.D18
BRIGHTNESS = 0.5

pixels = neopixel.NeoPixel(PIXEL_PIN, NUM_PIXELS, brightness=BRIGHTNESS, auto_write=False)

HR_MAC_LIST = [
    "E0:48:24:B5:48:92",  # Tomasz zegarek
    "F8:3F:4E:04:FB:2C",  # Tomasz pas COSPOO
    "14:13:0B:CB:A4:7D",  # Kasia zegarek
#    "F2:22:33:DD:11:CC",  # Kasia pas
]

HR_PROFILE_MAP = {
    "E0:48:24:B5:48:92": "tomasz",
    "F8:3F:4E:04:FB:2C": "tomasz",
    "14:13:0B:CB:A4:7D": "kasia",
#    "F2:22:33:DD:11:CC": "kasia",
}

# — STREFY TĘTNA (uniwersalne)
ZONE_COLORS = {
    "white":  (60, 60, 60),
    "blue":   (0, 102, 255),
    "green":  (0, 204, 0),
    "yellow": (255, 255, 102),
    "orange": (255, 165, 0),
    "red":    (255, 0, 0),
}

def get_zone(hr):
    if hr < 93:
        return "white"
    elif 93 <= hr < 111:
        return "blue"
    elif 111 <= hr < 130:
        return "green"
    elif 130 <= hr < 148:
        return "yellow"
    elif 148 <= hr < 167:
        return "orange"
    elif 167 <= hr <= 180:
        return "red"
    else:
        return "blink"

# === LOGGING ===
logging.basicConfig(
    filename="/home/pi/led/heart.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# === ANIMACJE ===

async def fade_from_center(target_color):
    center = NUM_PIXELS // 2
    max_offset = max(center, NUM_PIXELS - center)
    for offset in range(max_offset):
        i = center + offset
        j = center - offset
        if 0 <= i < NUM_PIXELS:
            pixels[i] = target_color
        if 0 <= j < NUM_PIXELS:
            pixels[j] = target_color
        pixels.show()
        await asyncio.sleep(0.003)
    pixels.fill(target_color)
    pixels.show()

async def blinking_red():
    while True:
        pixels.fill((255, 0, 0))
        pixels.show()
        await asyncio.sleep(0.5)
        pixels.fill((0, 0, 0))
        pixels.show()
        await asyncio.sleep(0.5)

# === IDLE MODES ===

async def idle_mode_1():
    bar = [(0, 102, 255)] * 8 + [(0, 204, 0)] * 8 + [(255, 255, 102)] * 8
    length = len(bar)
    pos = 0
    while True:
        pixels.fill((0, 0, 0))
        for i, color in enumerate(bar):
            idx = (pos + i) % NUM_PIXELS
            pixels[idx] = color
        pixels.show()
        await asyncio.sleep(0.05)
        pos = (pos + 1) % NUM_PIXELS

# dodatkowe tryby do testów (przykładowe puste definicje)
async def idle_mode_2():
    while True:
        pixels.fill((20, 20, 20))
        pixels.show()
        await asyncio.sleep(1)

async def idle_mode_3():
    while True:
        await asyncio.sleep(1)

async def idle_mode_4():
    colors = [
        (0, 51, 128),   # dark blue
        (0, 102, 255),  # blue
        (0, 204, 0),    # green
        (255, 255, 102) # yellow
    ]
    segment_len = 30
    direction = 1
    pos = 0

    gradient = []
    for i in range(segment_len):
        c_index = i * len(colors) // segment_len
        gradient.append(colors[c_index])

    while True:
        pixels.fill((0, 0, 0))  # Clear strip

        for i in range(segment_len):
            idx = pos + i
            if idx < NUM_PIXELS:
                pixels[idx] = gradient[i]

        pixels.show()
        await asyncio.sleep(0.03)

        pos += direction
        if pos + segment_len >= NUM_PIXELS or pos <= 0:
            direction *= -1

# === GŁÓWNA LOGIKA ===

current_task = None
last_zone = None

async def handle_hr(_, data, profile):
    global current_task, last_zone

    flags = data[0]
    hr = int.from_bytes(data[1:3], byteorder='little') if flags & 0x01 else data[1]

    logging.info(f"[{profile}] Tętno: {hr}")
    if hr < 30 or hr > 220:
        logging.warning("Tętno poza zakresem – ignoruję")
        return

    zone = get_zone(hr)
    if zone == last_zone:
        return
    last_zone = zone

    if current_task:
        current_task.cancel()
        try:
            await current_task
        except:
            pass

    if zone == "blink":
        current_task = asyncio.create_task(blinking_red())
    else:
        color = ZONE_COLORS[zone]
        current_task = asyncio.create_task(fade_from_center(color))

async def main():
    global current_task, last_zone
    last_zone = None
    current_task = asyncio.create_task(idle_mode_4())  # <- ZMIEN TUTAJ TRYB IDLE

    while True:
        logging.info("Szukam urządzenia HR...")
        devices = await BleakScanner.discover(timeout=10)
        found_device = next((d for d in devices if d.address in HR_MAC_LIST), None)

        if found_device:
            profile = HR_PROFILE_MAP[found_device.address]
            logging.info(f"Znaleziono urządzenie: {found_device.address} ({profile})")

            try:
                async with BleakClient(found_device.address) as client:
                    await client.start_notify(
                        "00002a37-0000-1000-8000-00805f9b34fb",
                        lambda sender, data: asyncio.create_task(handle_hr(sender, data, profile))
                    )

                    while client.is_connected:
                        await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"Błąd BLE: {type(e).__name__}: {e}")

        logging.warning("Rozłączono – wracam do idle")
        last_zone = None
        if current_task:
            current_task.cancel()
            try:
                await current_task
            except:
                pass
        current_task = asyncio.create_task(idle_mode_1())
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pixels.fill((0, 0, 0))
        pixels.show()
        print("Wyłączono")
