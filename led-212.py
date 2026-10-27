#!/usr/bin/env python3
"""Control a 212-pixel NeoPixel strip using BLE heart-rate data."""

import asyncio
import json
import logging
import os
import re
import socket
import sys
import traceback

import board
import neopixel
from bleak import BleakClient, BleakScanner


# Hardware configuration
NUM_PIXELS = 212
PIXEL_PIN = board.D18
BRIGHTNESS = 0.5
PIXEL_ORDER = neopixel.GRB

# LED numbers are one-based. The program animates LEDs 9–212 inclusive.
ACTIVE_START = 8  # Python index for LED 9
ACTIVE_STOP = NUM_PIXELS  # exclusive end index: 212
ANIMATION_STEP = 4  # Update less often to reduce CPU load.
TOP_START = 111  # Python index for LED 112
TOP_STOP = 151  # Exclusive end index: LED 151
TOP_RUNNER_LENGTH = 3
TOP_RUNNER_DELAY = 0.08
WHITE = (255, 255, 255)

HR_MAC = "DF:44:B1:5D:B8:DC"  # HRM Belt 28911
HR_PROFILE = "HRM Belt 28911"
HEART_RATE_CHARACTERISTIC = "00002a37-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_SERVICE = "00001818-0000-1000-8000-00805f9b34fb"
FTMS_SERVICE = "00001826-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_CHARACTERISTIC = "00002a63-0000-1000-8000-00805f9b34fb"
INDOOR_BIKE_DATA_CHARACTERISTIC = "00002ad2-0000-1000-8000-00805f9b34fb"
SCAN_TIMEOUT_SECONDS = 10
RETRY_DELAY_SECONDS = 5
CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8765

BLACK = (0, 0, 0)
ZONE_COLORS = {
    "white": (60, 60, 60),
    "blue": (0, 102, 255),
    "green": (0, 204, 0),
    "yellow": (255, 255, 102),
    "orange": (255, 165, 0),
    "red": (255, 0, 0),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

pixels = None
current_task = None
last_zone = None
active_mode = "hr"
last_active_mode = "hr"
latest_hr = None
latest_power = None
night_color = (255, 150, 80)
night_brightness = 0.08
render_event = None
mode_event = None
hr_connected = False
power_connected = False


def set_control(payload):
    global active_mode, last_active_mode, night_color, night_brightness

    mode = payload.get("mode")
    if mode not in {"toggle", "off", "hr", "power", "demo", "night", "top_scan"}:
        raise ValueError("Nieznany tryb.")
    if mode == "toggle":
        if active_mode == "off":
            active_mode = last_active_mode
        else:
            last_active_mode = active_mode
            active_mode = "off"
    elif mode == "off":
        if active_mode != "off":
            last_active_mode = active_mode
        active_mode = "off"
    else:
        active_mode = mode
        last_active_mode = mode

    color = payload.get("color")
    if color is not None:
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Kolor musi mieć format #RRGGBB.")
        night_color = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))

    brightness = payload.get("brightness")
    if brightness is not None:
        night_brightness = max(0.01, min(0.25, float(brightness)))

    render_event.set()
    mode_event.set()


def get_status():
    return {
        "mode": active_mode,
        "hr": latest_hr,
        "power_w": latest_power,
        "hr_connected": hr_connected,
        "power_connected": power_connected,
        "power_source": "BLE Cycling Power / FTMS",
        "night_color": "#%02x%02x%02x" % night_color,
        "night_brightness": night_brightness,
    }


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


async def systemd_watchdog():
    """Keep systemd informed that the asyncio controller loop is responsive."""
    try:
        watchdog_usec = int(os.environ.get("WATCHDOG_USEC", "0"))
    except ValueError:
        return
    if watchdog_usec <= 0:
        return

    interval = max(1.0, watchdog_usec / 3_000_000)
    while True:
        await asyncio.sleep(interval)
        systemd_notify("WATCHDOG=1")


async def handle_control_client(reader, writer):
    """Local API for the web server; this process remains the sole LED controller."""
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=3)
        parts = request_line.decode("ascii", "replace").strip().split()
        if len(parts) != 3:
            return
        method, path, _version = parts
        headers = {}
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=3)
            if line in (b"\r\n", b"\n", b""):
                break
            key, separator, value = line.decode("ascii", "replace").partition(":")
            if separator:
                headers[key.lower()] = value.strip()

        status = 200
        result = get_status()
        if method == "POST" and path == "/control":
            length = min(int(headers.get("content-length", "0")), 2048)
            payload = json.loads((await reader.readexactly(length)).decode("utf-8"))
            set_control(payload)
            result = get_status()
        elif method != "GET" or path != "/status":
            status = 404
            result = {"error": "Nie znaleziono endpointu."}

        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        reason = "OK" if status == 200 else "Not Found"
        writer.write(
            f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii")
            + body
        )
        await writer.drain()
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, ValueError, json.JSONDecodeError) as error:
        body = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
        writer.write(
            f"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii")
            + body
        )
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def wait_for_mode_change(timeout=None):
    try:
        await asyncio.wait_for(mode_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return
    mode_event.clear()


def get_zone(hr):
    if hr < 93:
        return "white"
    if hr < 111:
        return "blue"
    if hr < 130:
        return "green"
    if hr < 148:
        return "yellow"
    if hr < 167:
        return "orange"
    if hr <= 180:
        return "red"
    return "blink"


def fill_active(color):
    """Update only LEDs 9–212; leave the LEDs outside the frame untouched."""
    for index in range(ACTIVE_START, ACTIVE_STOP):
        pixels[index] = color


async def fade_from_center(target_color):
    center = (ACTIVE_START + ACTIVE_STOP - 1) // 2
    max_offset = max(center - ACTIVE_START, ACTIVE_STOP - 1 - center)

    for offset in range(0, max_offset + 1, ANIMATION_STEP):
        for index in (center + offset, center - offset):
            if ACTIVE_START <= index < ACTIVE_STOP:
                pixels[index] = target_color
        pixels.show()
        await asyncio.sleep(0.012)

    fill_active(target_color)
    pixels.show()


async def blinking_red():
    while True:
        fill_active(ZONE_COLORS["red"])
        pixels.show()
        await asyncio.sleep(0.5)
        fill_active(BLACK)
        pixels.show()
        await asyncio.sleep(0.5)


def paint_power(watts):
    """Map 100–300 W to a blue-to-red gradient."""
    fraction = max(0.0, min(1.0, (watts - 100) / 200))
    color = (int(255 * fraction), 0, int(255 * (1 - fraction)))
    fill_active(color)
    pixels.show()


async def demo_animation():
    colors = [(0, 90, 255), (0, 210, 100), (255, 70, 15), (150, 30, 220)]
    while True:
        for color in colors:
            await fade_from_center(color)
            await asyncio.sleep(2)


async def top_scan_animation():
    """Move a short white runner from left to right along LEDs 112–151."""
    fill_active(BLACK)
    width = TOP_STOP - TOP_START
    for position in range(width):
        for index in range(TOP_START, TOP_STOP):
            pixels[index] = BLACK
        for offset in range(TOP_RUNNER_LENGTH):
            index = TOP_START + ((position + offset) % width)
            pixels[index] = WHITE
        pixels.show()
        await asyncio.sleep(TOP_RUNNER_DELAY)


async def render_modes():
    global current_task

    while True:
        await render_event.wait()
        render_event.clear()
        await cancel_current_task()
        pixels.brightness = BRIGHTNESS

        if active_mode == "off":
            fill_active(BLACK)
            pixels.show()
        elif active_mode == "hr":
            if latest_hr is None:
                fill_active(BLACK)
                pixels.show()
            else:
                zone = get_zone(latest_hr)
                current_task = asyncio.create_task(
                    blinking_red() if zone == "blink" else fade_from_center(ZONE_COLORS[zone])
                )
        elif active_mode == "power":
            if latest_power is None:
                fill_active(BLACK)
                pixels.show()
            else:
                paint_power(latest_power)
        elif active_mode == "demo":
            current_task = asyncio.create_task(demo_animation())
        elif active_mode == "night":
            pixels.brightness = night_brightness
            fill_active(night_color)
            pixels.show()
        elif active_mode == "top_scan":
            current_task = asyncio.create_task(top_scan_animation())


async def cancel_current_task():
    global current_task

    task = current_task
    current_task = None
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def on_heart_rate(_sender, data):
    """Parse BLE measurements and start an animation only when the zone changes."""
    global current_task, last_zone, latest_hr

    if not data:
        logging.warning("Odebrano pusty pomiar tętna.")
        return

    flags = data[0]
    if flags & 0x01:
        if len(data) < 3:
            logging.warning("Odebrano niepełny 16-bitowy pomiar tętna.")
            return
        hr = int.from_bytes(data[1:3], byteorder="little")
    else:
        if len(data) < 2:
            logging.warning("Odebrano niepełny pomiar tętna.")
            return
        hr = data[1]

    if not 30 <= hr <= 220:
        logging.warning("Pomijam nieprawidłowe tętno: %s BPM", hr)
        return

    latest_hr = hr
    if active_mode != "hr":
        return

    zone = get_zone(hr)
    if zone == last_zone:
        return
    last_zone = zone
    logging.info("[%s] Tętno: %s BPM, strefa: %s", HR_PROFILE, hr, zone)

    # Bleak callbacks run on the asyncio loop. Cancel the previous effect
    # instead of creating a new task for every measurement.
    if current_task is not None and not current_task.done():
        current_task.cancel()

    if zone == "blink":
        current_task = asyncio.create_task(blinking_red())
    else:
        current_task = asyncio.create_task(fade_from_center(ZONE_COLORS[zone]))


def parse_indoor_bike_power(data):
    if len(data) < 2:
        return None
    flags = int.from_bytes(data[:2], "little")
    offset = 2
    if not flags & 0x0001:  # Instantaneous speed field
        offset += 2
    for flag, size in ((0x0002, 2), (0x0004, 2), (0x0008, 2), (0x0010, 3), (0x0020, 2)):
        if flags & flag:
            offset += size
    if flags & 0x0040 and len(data) >= offset + 2:
        return int.from_bytes(data[offset : offset + 2], "little", signed=True)
    return None


def on_power_data(_sender, data):
    global latest_power

    if len(data) < 4:
        return
    watts = int.from_bytes(data[2:4], "little", signed=True)
    if not 0 <= watts <= 3000:
        return
    latest_power = watts
    if active_mode == "power":
        paint_power(watts)


def on_indoor_bike_data(_sender, data):
    global latest_power

    watts = parse_indoor_bike_power(data)
    if watts is None or not 0 <= watts <= 3000:
        return
    latest_power = watts
    if active_mode == "power":
        paint_power(watts)


async def find_hr_device(timeout=SCAN_TIMEOUT_SECONDS):
    """Find the sensor without retaining every device seen during the scan."""
    found = asyncio.Event()
    result = None

    def on_advertisement(device, _advertisement_data):
        nonlocal result
        if device.address.upper() == HR_MAC.upper():
            result = device
            found.set()

    scanner = BleakScanner(detection_callback=on_advertisement)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return None
    finally:
        await scanner.stop()

    return result


async def find_power_device(timeout=SCAN_TIMEOUT_SECONDS):
    """Automatically detect Cycling Power meters and FTMS trainers."""
    found = asyncio.Event()
    result = None

    def on_advertisement(device, advertisement_data):
        nonlocal result
        advertised = " ".join(advertisement_data.service_uuids or []).lower()
        if "00001818" in advertised or "00001826" in advertised:
            result = device
            found.set()

    scanner = BleakScanner(detection_callback=on_advertisement)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return None
    finally:
        await scanner.stop()
    return result


async def ble_worker():
    """Use one BLE scanner/connection at a time, according to the selected mode."""
    global hr_connected, power_connected, latest_hr, latest_power, last_zone

    while True:
        mode = active_mode
        if mode not in {"hr", "power"}:
            await wait_for_mode_change()
            continue
        try:
            device = await (find_hr_device() if mode == "hr" else find_power_device())
            if device is None:
                label = "paska HR" if mode == "hr" else "miernika mocy BLE (Cycling Power/FTMS)"
                logging.info("Nie znaleziono %s; ponawiam skan.", label)
            elif active_mode == mode:
                logging.info("Znaleziono urządzenie BLE: %s", device.address)
                async with BleakClient(device) as client:
                    if mode == "hr":
                        await client.start_notify(HEART_RATE_CHARACTERISTIC, on_heart_rate)
                        hr_connected = True
                        logging.info("Połączono z paskiem HR.")
                    else:
                        callback = None
                        for characteristic, handler in (
                            (CYCLING_POWER_CHARACTERISTIC, on_power_data),
                            (INDOOR_BIKE_DATA_CHARACTERISTIC, on_indoor_bike_data),
                        ):
                            try:
                                await client.start_notify(characteristic, handler)
                                callback = handler
                                break
                            except Exception:
                                continue
                        if callback is None:
                            raise RuntimeError("Urządzenie nie udostępnia Cycling Power ani FTMS.")
                        power_connected = True
                        logging.info("Połączono z czujnikiem mocy BLE.")
                    while client.is_connected and active_mode == mode:
                        await asyncio.sleep(1)
        except Exception:
            logging.exception("Połączenie lub odczyt BLE nie powiódł się.")
        finally:
            if mode == "hr":
                hr_connected = False
                latest_hr = None
                last_zone = None
            else:
                power_connected = False
                latest_power = None
            if active_mode == mode:
                render_event.set()
        if active_mode == mode:
            await wait_for_mode_change(RETRY_DELAY_SECONDS)


async def main():
    global pixels, last_zone, render_event, mode_event

    # Initialize inside try/finally to release resources even after an error.
    pixels = neopixel.NeoPixel(
        PIXEL_PIN,
        NUM_PIXELS,
        brightness=BRIGHTNESS,
        auto_write=False,
        pixel_order=PIXEL_ORDER,
    )
    fill_active(BLACK)
    pixels.show()
    render_event = asyncio.Event()
    mode_event = asyncio.Event()
    render_event.set()

    try:
        api_server = await asyncio.start_server(handle_control_client, CONTROL_HOST, CONTROL_PORT)
        logging.info("Lokalne API sterowania działa na %s:%s.", CONTROL_HOST, CONTROL_PORT)
        async with api_server:
            systemd_notify("READY=1\nSTATUS=LED controller and local API ready")
            await asyncio.gather(render_modes(), ble_worker(), systemd_watchdog())
    finally:
        systemd_notify("STOPPING=1")
        last_zone = None
        await cancel_current_task()
        if pixels is not None:
            try:
                # Turn off only the frame LEDs; leave the tail outside the frame untouched.
                fill_active(BLACK)
                pixels.show()
            finally:
                pixels.deinit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Wyłączono.")
    except Exception:
        logging.error("Aplikacja zakończyła się błędem.")
        traceback.print_exc()
        sys.exit(1)
