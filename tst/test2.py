import board
import neopixel
import time

NUM_PIXELS = 2
pixels = neopixel.NeoPixel(board.D18, NUM_PIXELS, brightness=0.5, auto_write=False)

colors = [
    (255, 0, 0),   # Red
    (0, 255, 0),   # Green
    (0, 0, 255),   # Blue
    (0, 0, 0)      # Off
]

while True:
    for color in colors:
        pixels.fill(color)
        pixels.show()
        time.sleep(2)
