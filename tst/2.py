import board
import neopixel
import time
from datetime import datetime

pixels = neopixel.NeoPixel(board.D18, 2, brightness=0.5, auto_write=True)

while True:
    now = datetime.now()
    hour = now.hour % 12
    minute = now.minute

    # Skala: 0-255
    pixels[0] = (hour * 21, 0, 255 - hour * 21)       # zegar – od niebieskiego do czerwonego
    pixels[1] = (0, minute * 4, 255 - minute * 4)      # minuta – od niebieskiego do zielonego
    time.sleep(30)
