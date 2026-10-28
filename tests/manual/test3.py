import time
import board
import neopixel

pixels = neopixel.NeoPixel(board.D18, 2, brightness=0.4, auto_write=False)

while True:
    pixels.fill((255, 0, 0))
    pixels.show()
    time.sleep(1)
    pixels.fill((0, 255, 0))
    pixels.show()
    time.sleep(1)
    pixels.fill((0, 0, 255))
    pixels.show()
    time.sleep(1)
