import board
import neopixel

pixels = neopixel.NeoPixel(board.D18, 212, auto_write=True)
pixels.fill((0, 0, 0))
