import board
import neopixel
import time

LED_COUNT = 57
LED_PIN = board.D18
BRIGHTNESS = 0.5
DELAY = 2  # sekundy

colors = [
    (0, 0, 255),      # Blue – strefa 1
    (0, 255, 0),      # Green – strefa 2
    (255, 150, 0),    # Yellow – strefa 3
    (255, 0, 0),      # Red – strefa 4
    (255, 255, 255)   # White – strefa 5
]

pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=BRIGHTNESS, auto_write=False, pixel_order=neopixel.GRB)

def fade_to_color(current, target, steps=50, delay=0.03):
    for i in range(steps + 1):
        intermediate = tuple(
            int(current[j] + (target[j] - current[j]) * i / steps)
            for j in range(3)
        )
        pixels.fill(intermediate)
        pixels.show()
        time.sleep(delay)

current_color = (0, 0, 0)
pixels.fill(current_color)
pixels.show()
time.sleep(1)

while True:
    for target_color in colors:
        fade_to_color(current_color, target_color)
        current_color = target_color
        time.sleep(DELAY)
