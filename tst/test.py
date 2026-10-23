import time
from rpi_ws281x import PixelStrip, Color

# LED configuration
LED_COUNT = 2         # liczba diod
LED_PIN = 18          # GPIO18 (Pin 12)
LED_FREQ_HZ = 800000  # częstotliwość sygnału
LED_DMA = 10
LED_BRIGHTNESS = 64   # od 0 do 255
LED_INVERT = False
LED_CHANNEL = 0

# Inicjalizacja
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Test animacji
def color_wipe(color, wait_ms=500):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)

# Przykład
color_wipe(Color(255, 0, 0))  # czerwony
time.sleep(1)
color_wipe(Color(0, 255, 0))  # zielony
time.sleep(1)
color_wipe(Color(0, 0, 255))  # niebieski
