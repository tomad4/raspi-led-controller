#!/usr/bin/env python3
"""Sterowanie taśmą 212 NeoPixel na podstawie tętna z BLE."""

import asyncio
import logging
import sys
import traceback

import board
import neopixel
from bleak import BleakClient, BleakScanner


# Konfiguracja sprzętu
NUM_PIXELS = 212
PIXEL_PIN = board.D18
BRIGHTNESS = 0.5
PIXEL_ORDER = neopixel.GRB

# Numery LED są liczone od 1. Program animuje diody 9–212 włącznie.
ACTIVE_START = 8  # indeks Python dla LED nr 9
ACTIVE_STOP = NUM_PIXELS  # koniec zakresu wyłączny: indeks 212
ANIMATION_STEP = 4  # aktualizuj animację rzadziej, by ograniczyć obciążenie CPU

HR_MAC = "DF:44:B1:5D:B8:DC"  # HRM Belt 28911
HR_PROFILE = "HRM Belt 28911"
HEART_RATE_CHARACTERISTIC = "00002a37-0000-1000-8000-00805f9b34fb"
SCAN_TIMEOUT_SECONDS = 10
RETRY_DELAY_SECONDS = 5

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
    """Zmień wyłącznie LED nr 9–212; zakres poza ramką pozostaje nietknięty."""
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
    """Lekki callback BLE: parsuje pomiar i uruchamia animację tylko po zmianie strefy."""
    global current_task, last_zone

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

    zone = get_zone(hr)
    if zone == last_zone:
        return
    last_zone = zone
    logging.info("[%s] Tętno: %s BPM, strefa: %s", HR_PROFILE, hr, zone)

    # Callback Bleak działa w pętli asyncio. Anulowanie poprzedniego efektu
    # bez tworzenia dodatkowego zadania dla każdego pomiaru ogranicza narzut.
    if current_task is not None and not current_task.done():
        current_task.cancel()

    if zone == "blink":
        current_task = asyncio.create_task(blinking_red())
    else:
        current_task = asyncio.create_task(fade_from_center(ZONE_COLORS[zone]))


async def find_hr_device(timeout=SCAN_TIMEOUT_SECONDS):
    """Znajdź czujnik bez tworzenia listy wszystkich urządzeń z całego skanu."""
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


async def main():
    global pixels, last_zone

    # Inicjalizacja wewnątrz try/finally zapewnia sprzątanie także po błędzie.
    pixels = neopixel.NeoPixel(
        PIXEL_PIN,
        NUM_PIXELS,
        brightness=BRIGHTNESS,
        auto_write=False,
        pixel_order=PIXEL_ORDER,
    )
    fill_active(BLACK)
    pixels.show()

    try:
        while True:
            logging.info("Szukam czujnika tętna BLE...")
            try:
                device = await find_hr_device()
            except Exception:
                logging.exception("Błąd skanowania BLE.")
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue

            if device is None:
                logging.info("Nie znaleziono czujnika; ponawiam za %s s.", RETRY_DELAY_SECONDS)
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue

            logging.info("Znaleziono czujnik HR: %s", device.address)
            try:
                async with BleakClient(device) as client:
                    await client.start_notify(HEART_RATE_CHARACTERISTIC, on_heart_rate)
                    logging.info("Połączono; oczekuję na pomiary tętna.")
                    while client.is_connected:
                        await asyncio.sleep(5)
            except Exception:
                logging.exception("Połączenie BLE przerwane lub nieudane.")

            last_zone = None
            await cancel_current_task()
            fill_active(BLACK)
            pixels.show()
            logging.info("Rozłączono; ponawiam wyszukiwanie za %s s.", RETRY_DELAY_SECONDS)
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    finally:
        last_zone = None
        await cancel_current_task()
        if pixels is not None:
            try:
                # Końcowe wyłączenie całego łańcucha dla bezpiecznego zamknięcia.
                pixels.fill(BLACK)
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
