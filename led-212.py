#!/usr/bin/env python3
"""Control a 212-pixel NeoPixel strip using BLE heart-rate data."""

import asyncio
import json
import logging
import math
import os
import re
import socket
import sys

from app_logging import configure_app_logging
from settings.config import CONNECTION_SETTINGS, STRIP_SETTINGS

configure_app_logging("led-212")

import board
import neopixel
from bleak import BleakClient, BleakScanner


# Hardware settings are editable in settings/strip.json. Config ranges use
# one-based, inclusive LED numbers; these indexes use Python's zero-based form.
NUM_PIXELS = int(STRIP_SETTINGS["pixel_count"])
PIXEL_PIN = getattr(board, f"D{int(STRIP_SETTINGS['gpio_pin'])}")
BRIGHTNESS = float(STRIP_SETTINGS["brightness"])
PIXEL_ORDER = getattr(neopixel, STRIP_SETTINGS["pixel_order"])
ACTIVE_START = int(STRIP_SETTINGS["active_range"][0]) - 1
ACTIVE_STOP = int(STRIP_SETTINGS["active_range"][1])
TOP_RANGE = STRIP_SETTINGS["segments"].get("top", [112, 151])
TOP_START = int(TOP_RANGE[0]) - 1
TOP_STOP = int(TOP_RANGE[1])
ANIMATION_STEP = int(STRIP_SETTINGS["animation"]["step"])
TOP_RUNNER_LENGTH = int(STRIP_SETTINGS["animation"]["runner_length"])
TOP_RUNNER_DELAY = float(STRIP_SETTINGS["animation"]["runner_delay_seconds"])
HR_ZONE_TRANSITION_SECONDS = 0.4
HR_PULSE_PERIOD_SECONDS = 1.0
HR_PULSE_AMPLITUDE = 0.25
HR_PULSE_FRAME_DELAY = 0.05
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

BLE_SETTINGS = CONNECTION_SETTINGS.get("ble", {})
HR_DEVICE_PROFILES = {
    profile_id: {
        **profile,
        "names": tuple(profile.get("names", ())),
        **({"address": profile["address"].upper()} if profile.get("address") else {}),
    }
    for profile_id, profile in CONNECTION_SETTINGS.get("heart_rate_profiles", {}).items()
}
if not HR_DEVICE_PROFILES:
    raise ValueError("No heart-rate profiles configured in settings/connections.json")
HEART_RATE_CHARACTERISTIC = BLE_SETTINGS.get(
    "heart_rate_characteristic", "00002a37-0000-1000-8000-00805f9b34fb"
)
CYCLING_POWER_SERVICE = BLE_SETTINGS.get(
    "cycling_power_service", "00001818-0000-1000-8000-00805f9b34fb"
)
FTMS_SERVICE = BLE_SETTINGS.get("ftms_service", "00001826-0000-1000-8000-00805f9b34fb")
CYCLING_POWER_CHARACTERISTIC = BLE_SETTINGS.get(
    "cycling_power_characteristic", "00002a63-0000-1000-8000-00805f9b34fb"
)
INDOOR_BIKE_DATA_CHARACTERISTIC = BLE_SETTINGS.get(
    "indoor_bike_data_characteristic", "00002ad2-0000-1000-8000-00805f9b34fb"
)
SCAN_TIMEOUT_SECONDS = int(BLE_SETTINGS.get("scan_timeout_seconds", 10))
RETRY_DELAY_SECONDS = int(BLE_SETTINGS.get("retry_delay_seconds", 5))
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

pixels = None
current_task = None
hr_animation_task = None
last_zone = None
active_mode = "hr"
last_active_mode = "hr"
hr_device_choice = next(iter(HR_DEVICE_PROFILES))
latest_hr = None
latest_power = None
hr_zone_color = BLACK
hr_display_color = BLACK
night_color = (255, 150, 80)
night_brightness = 0.08
render_event = None
mode_event = None
hr_connected = False
power_connected = False


def set_control(payload):
    global active_mode, last_active_mode, hr_device_choice, night_color, night_brightness
    global last_zone, hr_zone_color, hr_display_color

    previous_mode = active_mode
    mode = payload.get("mode")
    if mode not in {"toggle", "off", "hr", "power", "demo", "night", "top_scan"}:
        raise ValueError("Nieznany tryb.")
    device_choice = payload.get("hr_device")
    if device_choice is not None:
        if device_choice not in HR_DEVICE_PROFILES:
            raise ValueError("Nieznane urządzenie HR.")
        hr_device_choice = device_choice
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

    if active_mode == "hr" and previous_mode != "hr":
        last_zone = None
        hr_zone_color = BLACK
        hr_display_color = BLACK

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
        "hr_device": hr_device_choice,
        "hr_device_label": HR_DEVICE_PROFILES[hr_device_choice]["label"],
        "hr_devices": [
            {"id": device_id, "label": profile["label"]}
            for device_id, profile in HR_DEVICE_PROFILES.items()
        ],
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
    return "red"


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


async def hr_zone_animation():
    """Blend between HR zones while breathing at 60 BPM."""
    global hr_zone_color, hr_display_color, hr_animation_task

    task = asyncio.current_task()
    loop = asyncio.get_running_loop()
    started_at = loop.time()
    transition_target = hr_zone_color
    transition_start = hr_display_color
    transition_started_at = started_at

    try:
        while active_mode == "hr":
            now = loop.time()
            if transition_target != hr_zone_color:
                transition_target = hr_zone_color
                transition_start = hr_display_color
                transition_started_at = now

            progress = min(1.0, (now - transition_started_at) / HR_ZONE_TRANSITION_SECONDS)
            hr_display_color = tuple(
                round(start + (target - start) * progress)
                for start, target in zip(transition_start, transition_target)
            )

            pulse = 1.0 + HR_PULSE_AMPLITUDE * math.sin(
                2 * math.pi * (now - started_at) / HR_PULSE_PERIOD_SECONDS
            )
            pixels.brightness = max(0.0, min(1.0, BRIGHTNESS * pulse))
            fill_active(hr_display_color)
            pixels.show()
            await asyncio.sleep(HR_PULSE_FRAME_DELAY)
    finally:
        if hr_animation_task is task:
            hr_animation_task = None


def start_hr_zone_animation():
    """Ensure one persistent HR color and pulse animation is running."""
    global current_task, hr_animation_task

    if hr_animation_task is not None and not hr_animation_task.done():
        return
    if current_task is not None and not current_task.done():
        current_task.cancel()
    hr_animation_task = asyncio.create_task(hr_zone_animation())
    current_task = hr_animation_task


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


async def running_lights(start, stop, color):
    """Bounce a three-pixel runner between the ends of a selected LED segment."""
    fill_active(BLACK)
    width = stop - start
    max_position = width - TOP_RUNNER_LENGTH
    positions = list(range(max_position + 1))
    positions.extend(range(max_position - 1, 0, -1))

    while True:
        for position in positions:
            for index in range(start, stop):
                pixels[index] = BLACK
            for offset in range(TOP_RUNNER_LENGTH):
                index = start + position + offset
                pixels[index] = color
            pixels.show()
            await asyncio.sleep(TOP_RUNNER_DELAY)


async def top_scan_animation():
    """Move a short white runner from left to right along LEDs 112–151."""
    await running_lights(TOP_START, TOP_STOP, WHITE)


async def waiting_hr_animation():
    """Show a red runner on the upper frame while waiting for heart-rate data."""
    await running_lights(TOP_START, TOP_STOP, RED)


async def waiting_power_animation():
    """Show a blue runner on the top edge while waiting for power data."""
    await running_lights(TOP_START, TOP_STOP, BLUE)


async def render_modes():
    global hr_zone_color

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
                current_task = asyncio.create_task(waiting_hr_animation())
            else:
                hr_zone_color = ZONE_COLORS[get_zone(latest_hr)]
                start_hr_zone_animation()
        elif active_mode == "power":
            if latest_power is None:
                current_task = asyncio.create_task(waiting_power_animation())
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
    global current_task, hr_animation_task

    task = current_task
    current_task = None
    if task is hr_animation_task:
        hr_animation_task = None
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def on_heart_rate(_sender, data):
    """Parse BLE measurements and update the active HR zone color."""
    global last_zone, latest_hr, hr_zone_color

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
        start_hr_zone_animation()
        return
    last_zone = zone
    hr_zone_color = ZONE_COLORS[zone]
    logging.info(
        "[%s] Tętno: %s BPM, strefa: %s",
        HR_DEVICE_PROFILES[hr_device_choice]["label"],
        hr,
        zone,
    )

    # Keep one pulsing task alive; it reads the new zone color on its next frame.
    start_hr_zone_animation()


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
    global current_task, latest_power

    if len(data) < 4:
        return
    watts = int.from_bytes(data[2:4], "little", signed=True)
    if not 0 <= watts <= 3000:
        return
    latest_power = watts
    if active_mode == "power":
        if current_task is not None and not current_task.done():
            current_task.cancel()
            current_task = None
        paint_power(watts)


def on_indoor_bike_data(_sender, data):
    global current_task, latest_power

    watts = parse_indoor_bike_power(data)
    if watts is None or not 0 <= watts <= 3000:
        return
    latest_power = watts
    if active_mode == "power":
        if current_task is not None and not current_task.done():
            current_task.cancel()
            current_task = None
        paint_power(watts)


async def find_hr_device(device_choice, timeout=SCAN_TIMEOUT_SECONDS):
    """Find a selected heart-rate sensor by its advertised name or address."""
    found = asyncio.Event()
    result = None
    profile = HR_DEVICE_PROFILES[device_choice]

    def on_advertisement(device, advertisement_data):
        nonlocal result
        name = (advertisement_data.local_name or device.name or "").lower()
        address = device.address.upper()
        expected_address = profile.get("address", "").upper()
        matching_name = any(
            re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", name)
            for token in profile["names"]
        )
        if (expected_address and address == expected_address) or matching_name:
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
        advertised = " ".join(
            service.lower().replace("-", "") for service in (advertisement_data.service_uuids or [])
        )
        power_uuid = CYCLING_POWER_SERVICE.lower().replace("-", "")[:8]
        ftms_uuid = FTMS_SERVICE.lower().replace("-", "")[:8]
        if power_uuid in advertised or ftms_uuid in advertised:
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
    global hr_zone_color, hr_display_color

    while True:
        mode = active_mode
        selected_hr_device = hr_device_choice
        if mode not in {"hr", "power"}:
            await wait_for_mode_change()
            continue
        try:
            device = await (
                find_hr_device(selected_hr_device) if mode == "hr" else find_power_device()
            )
            if device is None:
                label = (
                    HR_DEVICE_PROFILES[selected_hr_device]["label"]
                    if mode == "hr"
                    else "miernika mocy BLE (Cycling Power/FTMS)"
                )
                logging.info("Nie znaleziono %s; ponawiam skan.", label)
            elif active_mode == mode and (mode != "hr" or hr_device_choice == selected_hr_device):
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
                    while (
                        client.is_connected
                        and active_mode == mode
                        and (mode != "hr" or hr_device_choice == selected_hr_device)
                    ):
                        await asyncio.sleep(1)
        except Exception:
            logging.exception("Połączenie lub odczyt BLE nie powiódł się.")
        finally:
            if mode == "hr":
                hr_connected = False
                latest_hr = None
                last_zone = None
                hr_zone_color = BLACK
                hr_display_color = BLACK
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
        logging.info("Wyłączono.")
    except Exception:
        logging.exception("Aplikacja zakończyła się błędem.")
        sys.exit(1)
