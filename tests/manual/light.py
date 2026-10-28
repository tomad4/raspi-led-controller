#!/usr/bin/env python3
"""Manually light a selected LED or range on a 212-pixel NeoPixel strip.

Examples (LED numbers are one-based):
    sudo /opt/led-venv/bin/python /opt/raspi-led-controller/tst/light.py -1
    sudo /opt/led-venv/bin/python /opt/raspi-led-controller/tst/light.py -1_3 -g
    sudo /opt/led-venv/bin/python /opt/raspi-led-controller/tst/light.py -20 -r

Red is used when no color flag is given. LEDs stay on until Ctrl+C.
On Raspberry Pi, GPIO control requires running with sudo.
"""

import re
import sys
import time
import traceback

import board
import neopixel


NUM_PIXELS = 212
PIXEL_PIN = board.D18  # GPIO18, physical pin 12
BRIGHTNESS = 0.12
PIXEL_ORDER = neopixel.GRB
COLORS = {
    "-r": (255, 0, 0),
    "-g": (0, 255, 0),
    "-b": (0, 0, 255),
}
SELECTOR_PATTERN = re.compile(r"-(\d+)(?:_(\d+))?\Z")


def usage():
    print(
        "Użycie: light.py -N[-M] [-r|-g|-b]\n"
        "  -N     zapala diodę N (numeracja od 1)\n"
        "  -N_M   zapala zakres od N do M włącznie\n"
        "  -r     czerwony; -g zielony; -b niebieski (domyślnie: czerwony)\n"
        "Przykłady: light.py -1 | light.py -1_3 -g | light.py -20 -r\n"
        "Wciśnij Ctrl+C, aby wyłączyć taśmę i zakończyć."
    )


def parse_arguments(arguments):
    if arguments in ([], ["-h"], ["--help"]):
        usage()
        return None

    selectors = []
    color_flags = []
    for argument in arguments:
        if argument in COLORS:
            color_flags.append(argument)
        else:
            match = SELECTOR_PATTERN.fullmatch(argument)
            if match is None:
                raise ValueError(f"Nieznany argument: {argument}")
            start = int(match.group(1))
            end = int(match.group(2) or start)
            if start < 1 or end > NUM_PIXELS:
                raise ValueError(f"Numer diody musi być w zakresie 1–{NUM_PIXELS}.")
            if start > end:
                raise ValueError("Początek zakresu musi być mniejszy lub równy końcowi.")
            selectors.append((start, end))

    if len(selectors) != 1:
        raise ValueError("Podaj dokładnie jedną diodę albo jeden zakres, np. -1 lub -1_3.")
    if len(color_flags) > 1:
        raise ValueError("Wybierz tylko jeden kolor: -r, -g albo -b.")

    start, end = selectors[0]
    color_flag = color_flags[0] if color_flags else "-r"
    return start, end, color_flag, COLORS[color_flag]


def main():
    try:
        selection = parse_arguments(sys.argv[1:])
        if selection is None:
            return 0
        start, end, color_flag, color = selection
    except ValueError as error:
        print(f"E: {error}", file=sys.stderr)
        usage()
        return 2

    pixels = None
    exit_code = 0
    try:
        pixels = neopixel.NeoPixel(
            PIXEL_PIN,
            NUM_PIXELS,
            brightness=BRIGHTNESS,
            auto_write=False,
            pixel_order=PIXEL_ORDER,
        )
        pixels.fill((0, 0, 0))
        for led_number in range(start, end + 1):
            pixels[led_number - 1] = color
        pixels.show()

        range_label = str(start) if start == end else f"{start}–{end}"
        print(
            f"Zapalone diody {range_label} z {NUM_PIXELS}, "
            f"kolor {color_flag[1:].upper()}, jasność {BRIGHTNESS:.0%}."
        )
        print("Wciśnij Ctrl+C, aby wyłączyć taśmę.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Kończę test.")
    except Exception:
        print("Błąd inicjalizacji lub sterowania taśmą:", file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    finally:
        if pixels is not None:
            try:
                pixels.fill((0, 0, 0))
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
