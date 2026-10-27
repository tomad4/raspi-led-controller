import time
from rpi_ws281x import PixelStrip, Color

# LED configuration
LED_COUNT = 2         # Number of LEDs.
LED_PIN = 18          # GPIO18 (physical pin 12).
LED_FREQ_HZ = 800000  # Signal frequency.
LED_DMA = 10
LED_BRIGHTNESS = 64   # Range: 0–255.
LED_INVERT = False
LED_CHANNEL = 0

# Initialization
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Animation test
def color_wipe(color, wait_ms=500):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)

# Example
color_wipe(Color(255, 0, 0))  # Red.
time.sleep(1)
color_wipe(Color(0, 255, 0))  # Green.
time.sleep(1)
color_wipe(Color(0, 0, 255))  # Blue.
