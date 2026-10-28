#!/usr/bin/env python3
"""Test animation for the LED frame: LEDs 10–212, top section 112–151.

LED numbers in comments and messages are one-based. LEDs 1–9
(the tail outside the frame) remain off.

Run in the existing virtual environment on Raspberry Pi:
    sudo /opt/led-venv/bin/python /opt/raspi-led-controller/tests/manual/test_frame_animation.py

Main frame effects change at random intervals of 10–15 seconds. The top section
has an independent moving light point. Press Ctrl+C to stop the test.
"""

import colorsys
import math
import random
import sys
import time
import traceback

import board
import neopixel


NUM_PIXELS = 212
PIXEL_PIN = board.D18  # GPIO18, physical pin 12
BRIGHTNESS = 0.12
PIXEL_ORDER = neopixel.GRB

FRAME_START = 10  # One-based numbering; LEDs 1–9 are outside the frame.
FRAME_END = 212
TOP_START = 112
TOP_END = 151

FRAME_RATE_SECONDS = 0.05
EFFECT_MIN_SECONDS = 10.0
EFFECT_MAX_SECONDS = 15.0
BLACK = (0, 0, 0)

EFFECTS = (
    ("gradient kolorów", "gradient"),
    ("oddech w błękicie", "breath"),
    ("przesuwające się pasy RGB", "rgb_bands"),
)


def hsv_color(hue, saturation=1.0, value=1.0):
    """Convert normalized HSV values (0–1) to an RGB color (0–255)."""
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return round(red * 255), round(green * 255), round(blue * 255)


def frame_color(effect, led_number, elapsed, effect_duration):
    position = led_number - FRAME_START
    frame_length = FRAME_END - FRAME_START + 1
    progress = position / max(frame_length - 1, 1)
    phase = elapsed / effect_duration

    if effect == "gradient":
        return hsv_color(0.53 + progress * 0.35 + phase * 0.25, 0.9, 0.75)

    if effect == "breath":
        level = 0.12 + 0.55 * (0.5 + 0.5 * math.sin(phase * 2 * math.pi))
        return hsv_color(0.58, 0.9, level)

    # Move the RGB bands along the frame section.
    band = int((position / 12 + phase * 5) % 3)
    colors = ((255, 0, 0), (0, 255, 0), (0, 0, 255))
    return tuple(round(channel * 0.65) for channel in colors[band])


def top_color(led_number, elapsed):
    """Create an independent comet effect for the top frame section, LEDs 112–151."""
    top_length = TOP_END - TOP_START + 1
    position = (1 + math.sin(2 * math.pi * elapsed / 5.0)) * 0.5 * (top_length - 1)
    distance = abs((led_number - TOP_START) - position)

    if distance < 1.0:
        return (150, 210, 255)
    if distance < 3.0:
        intensity = (3.0 - distance) / 3.0
        return (0, round(90 * intensity), round(150 * intensity))
    return (0, 0, 8)


def draw_frame(pixels, effect, elapsed, effect_duration):
    # Start each frame with black so the tail (LEDs 1–9) stays off.
    pixels.fill(BLACK)

    for led_number in range(FRAME_START, FRAME_END + 1):
        pixels[led_number - 1] = frame_color(
            effect, led_number, elapsed, effect_duration
        )

    # Give the top 40 LEDs an effect independent of the rest of the frame.
    for led_number in range(TOP_START, TOP_END + 1):
        pixels[led_number - 1] = top_color(led_number, elapsed)

    pixels.show()


def next_effect(previous_effect=None):
    choices = [effect for effect in EFFECTS if effect[1] != previous_effect]
    return random.choice(choices)


def run_animation(pixels):
    effect_name, effect = next_effect()
    effect_duration = random.uniform(EFFECT_MIN_SECONDS, EFFECT_MAX_SECONDS)
    effect_started = time.monotonic()
    print(
        f"Efekt: {effect_name} ({effect_duration:.1f} s); "
        f"góra ramki: diody {TOP_START}–{TOP_END}."
    )

    while True:
        now = time.monotonic()
        elapsed = now - effect_started
        if elapsed >= effect_duration:
            effect_name, effect = next_effect(effect)
            effect_duration = random.uniform(EFFECT_MIN_SECONDS, EFFECT_MAX_SECONDS)
            effect_started = now
            elapsed = 0.0
            print(f"Zmiana efektu: {effect_name} ({effect_duration:.1f} s).")

        draw_frame(pixels, effect, elapsed, effect_duration)
        time.sleep(FRAME_RATE_SECONDS)


def main():
    pixels = None
    exit_code = 0

    print(
        f"Test ramki: {FRAME_START}–{FRAME_END} z {NUM_PIXELS} diod; "
        f"ogonek 1–{FRAME_START - 1} wyłączony; jasność {BRIGHTNESS:.0%}."
    )
    print("Wciśnij Ctrl+C, aby zakończyć animację.")

    try:
        pixels = neopixel.NeoPixel(
            PIXEL_PIN,
            NUM_PIXELS,
            brightness=BRIGHTNESS,
            auto_write=False,
            pixel_order=PIXEL_ORDER,
        )
        run_animation(pixels)
    except KeyboardInterrupt:
        print("Kończę animację.")
    except Exception:
        print("Błąd inicjalizacji lub sterowania taśmą:", file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    finally:
        if pixels is not None:
            try:
                pixels.fill(BLACK)
                pixels.show()
            except Exception:
                print("Nie udało się wyłączyć diod:", file=sys.stderr)
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
