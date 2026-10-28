#!/usr/bin/env python3
"""Independent, low-brightness test for a 212-LED NeoPixel strip on Raspberry Pi.

Run in the existing virtual environment (GPIO18 requires root on Raspberry Pi):
    sudo /opt/led-venv/bin/python /opt/raspi-led-controller/tst/test_led_strip.py

This script does not use BLE or the main application. Brightness is limited to 12%.
"""

import importlib.metadata
import sys
import time
import traceback

import board
import neopixel


NUM_PIXELS = 212
PIXEL_PIN = board.D18  # GPIO18, physical pin 12
BRIGHTNESS = 0.12
PIXEL_ORDER = neopixel.GRB
PAUSE_SECONDS = 1.0
COLOR_SECONDS = 1.0
MOVING_DOT_STEPS = 32
MOVING_DOT_DELAY_SECONDS = 0.04

BLACK = (0, 0, 0)
COLORS = (
    ("czerwony", (255, 0, 0)),
    ("zielony", (0, 255, 0)),
    ("niebieski", (0, 0, 255)),
)


def print_configuration():
    try:
        version = importlib.metadata.version("adafruit-circuitpython-neopixel")
    except importlib.metadata.PackageNotFoundError:
        version = "wersja niedostępna w metadanych"

    print("Konfiguracja testu taśmy LED:")
    print(f"  Biblioteka: Adafruit CircuitPython NeoPixel {version} (przez Blinka)")
    print("  Backend na Raspberry Pi: neopixel_write / rpi_ws281x")
    print("  Pin danych: GPIO18 (board.D18, fizyczny pin 12)")
    print(f"  Liczba diod: {NUM_PIXELS}")
    print(f"  Kolejność kanałów: {PIXEL_ORDER}")
    print(f"  Jasność: {BRIGHTNESS:.0%}")
    print("  auto_write: False")
    print("  Częstotliwość, DMA i inwersja: sterowane przez backend Blinka;")
    print("    API NeoPixel użyte w tym skrypcie nie udostępnia ich jako parametrów.")
    print("  Wymagane uprawnienia: root (uruchom przez sudo).")


def send_black(pixels):
    pixels.fill(BLACK)
    pixels.show()


def run_test(pixels):
    print("Etap 1/6: czyszczenie taśmy.")
    send_black(pixels)
    time.sleep(PAUSE_SECONDS)

    for index, (name, color) in enumerate(COLORS, start=2):
        print(f"Etap {index}/6: wszystkie diody — {name}.")
        pixels.fill(color)
        pixels.show()
        time.sleep(COLOR_SECONDS)
        send_black(pixels)
        time.sleep(PAUSE_SECONDS)

    print("Etap 5/6: pojedyncze diody na początku, środku i końcu taśmy.")
    for position in (0, 106, 211):
        pixels[position] = (255, 255, 255)
        pixels.show()
        time.sleep(COLOR_SECONDS)
        send_black(pixels)
        time.sleep(0.4)
        print(f"  Sprawdzono indeks {position}.")

    print(f"Etap 6/6: ruchomy punkt ({MOVING_DOT_STEPS} kroków z {NUM_PIXELS}).")
    for position in range(MOVING_DOT_STEPS):
        send_black(pixels)
        pixels[position] = (255, 255, 255)
        pixels.show()
        time.sleep(MOVING_DOT_DELAY_SECONDS)

    print("Test zakończony.")


def main():
    pixels = None
    exit_code = 0

    print_configuration()
    try:
        pixels = neopixel.NeoPixel(
            PIXEL_PIN,
            NUM_PIXELS,
            brightness=BRIGHTNESS,
            auto_write=False,
            pixel_order=PIXEL_ORDER,
        )
        run_test(pixels)
    except KeyboardInterrupt:
        print("Przerwano przez użytkownika (Ctrl+C).")
    except Exception:
        print("Błąd inicjalizacji lub wysyłania danych:", file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    finally:
        if pixels is not None:
            try:
                print("Wyłączam diody i zwalniam zasoby.")
                send_black(pixels)
            except Exception:
                print("Nie udało się wysłać końcowego sygnału czerni:", file=sys.stderr)
                traceback.print_exc()
                exit_code = 1
            try:
                pixels.deinit()
            except Exception:
                print("Nie udało się zwolnić zasobów NeoPixel:", file=sys.stderr)
                traceback.print_exc()
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
