import board
import neopixel
import time

# Ustawienia paska LED
NUM_PIXELS = 2
BRIGHTNESS = 0.3
pixels = neopixel.NeoPixel(board.D18, NUM_PIXELS, brightness=BRIGHTNESS, auto_write=False, pixel_order=neopixel.GRB)

# Definicja kolorów stref
colors = {
    "1": (0, 0, 255),     # Niebieski
    "2": (0, 255, 0),     # Zielony
    "3": (255, 255, 0),   # Żółty
    "4": (255, 165, 0),   # Pomarańczowy
    "5": (255, 0, 0),     # Czerwony
    "0": (255, 255, 255), # Biały
}

def fade_to_color(start_color, end_color, steps=30, delay=0.02):
    for i in range(steps + 1):
        intermediate = tuple(
            int(start + (end - start) * i / steps)
            for start, end in zip(start_color, end_color)
        )
        pixels.fill(intermediate)
        pixels.show()
        time.sleep(delay)

def get_current_color():
    try:
        return pixels[0]
    except:
        return (0, 0, 0)

print("Wciśnij klawisz 1–5 lub 0 (biały), q – wyjście")

while True:
    user_input = input(">> ").strip()
    if user_input == "q":
        fade_to_color(get_current_color(), (0, 0, 0))  # Fade out przy wyjściu
        break
    elif user_input in colors:
        fade_to_color(get_current_color(), colors[user_input])
    else:
        print("Nieznana opcja – użyj 1–5, 0 lub q")
