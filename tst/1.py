import board
import neopixel
import time

pixels = neopixel.NeoPixel(board.D18, 2, brightness=0.5, auto_write=False)

colors = [
    (0, 0, 255),    # Blue — zone 1
    (0, 255, 0),    # Green — zone 2
    (255, 255, 0),  # Yellow — zone 3
    (255, 128, 0),  # Orange — zone 4
    (255, 0, 0),    # Red — zone 5
]

def fade_to(color, steps=50, delay=0.05):
    for i in range(steps + 1):
        r = int(color[0] * i / steps)
        g = int(color[1] * i / steps)
        b = int(color[2] * i / steps)
        pixels.fill((r, g, b))
        pixels.show()
        time.sleep(delay)

while True:
    for color in colors:
        fade_to(color)
        time.sleep(60)
