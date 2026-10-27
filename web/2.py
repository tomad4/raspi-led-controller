import board
import neopixel
import time
from datetime import datetime

pixels = neopixel.NeoPixel(board.D18, 2, brightness=0.5, auto_write=True)

while True:
    now = datetime.now()
    hour = now.hour % 12
    minute = now.minute

    # Scale: 0–255.
    pixels[0] = (hour * 21, 0, 255 - hour * 21)       # Clock — blue to red.
    pixels[1] = (0, minute * 4, 255 - minute * 4)      # Minute — blue to green.
    time.sleep(30)
