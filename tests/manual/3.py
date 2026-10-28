import board
import neopixel
import time

pixels = neopixel.NeoPixel(board.D18, 2, brightness=0.5, auto_write=True)

def wheel(pos):
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

i = 0
while True:
    pixels[0] = wheel(i % 256)
    pixels[1] = wheel((i + 40) % 256)
    i = (i + 5) % 256
    time.sleep(0.1)
