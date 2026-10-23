import board
import neopixel

pixels = neopixel.NeoPixel(board.D18, 239, auto_write=True)
pixels.fill((0, 0, 0))
