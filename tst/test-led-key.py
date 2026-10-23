import board
import neopixel

pixels = neopixel.NeoPixel(board.D18, 2, brightness=0.4, auto_write=True)

colors = {
    "1": (0, 0, 255),     # niebieski
    "2": (0, 255, 0),     # zielony
    "3": (255, 255, 0),   # żółty
    "4": (255, 165, 0),   # pomarańczowy
    "5": (255, 0, 0),     # czerwony
    "0": (255, 255, 255), # biały
    "q": (0, 0, 0)        # wyłącz
}

print("Wpisz numer strefy (1–5), 0 (biały), q (wyłącz). Ctrl+C kończy.")

try:
    while True:
        choice = input("Wybierz: ").strip()
        if choice in colors:
            pixels.fill(colors[choice])
        else:
            print("Niepoprawny wybór.")
except KeyboardInterrupt:
    pixels.fill((0, 0, 0))
    print("\nZakończono.")
