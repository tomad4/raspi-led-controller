import asyncio
import time
import board
import neopixel

NUM_PIXELS = 212
PIXEL_PIN = board.D18
BRIGHTNESS = 0.3  # Reduced brightness for testing.

pixels = neopixel.NeoPixel(PIXEL_PIN, NUM_PIXELS, brightness=BRIGHTNESS, auto_write=False)

# --- Idle effects ---

async def idle_mode_1():
    pos = 0
    colors = [(0, 102, 255), (0, 204, 0), (255, 255, 102)]
    while True:
        pixels.fill((0, 0, 0))
        for i in range(20):
            idx = (pos + i) % NUM_PIXELS
            pixels[idx] = colors[i % len(colors)]
        pixels.show()
        await asyncio.sleep(0.03)
        pos = (pos + 1) % NUM_PIXELS

async def idle_mode_2():
    color = (20, 20, 20)
    while True:
        for i in range(NUM_PIXELS):
            pixels.fill((0, 0, 0))
            pixels[i] = color
            pixels.show()
            await asyncio.sleep(0.05)

async def idle_mode_3():
    pos = 0
    direction = 1
    colors = [(0, 102, 255), (0, 204, 0), (255, 255, 102)] * 5
    segment_len = len(colors)
    while True:
        pixels.fill((0, 0, 0))
        for i, c in enumerate(colors):
            idx = pos + i
            if 0 <= idx < NUM_PIXELS:
                pixels[idx] = c
        pixels.show()
        await asyncio.sleep(0.03)
        pos += direction
        if pos + segment_len >= NUM_PIXELS or pos <= 0:
            direction *= -1

async def idle_mode_4():
    colors = [
        (0, 51, 128),   # dark blue
        (0, 102, 255),  # blue
        (0, 204, 0),    # green
        (255, 255, 102) # yellow
    ]
    segment_len = 20
    direction = 1
    pos = 0

    gradient = []
    for i in range(segment_len):
        c_index = i * len(colors) // segment_len
        gradient.append(colors[c_index])

    while True:
        pixels.fill((0, 0, 0))  # Clear strip

        for i in range(segment_len):
            idx = pos + i
            if idx < NUM_PIXELS:
                pixels[idx] = gradient[i]

        pixels.show()
        await asyncio.sleep(0.03)

        pos += direction
        if pos + segment_len >= NUM_PIXELS or pos <= 0:
            direction *= -1

# --- Main function ---

async def main():
    modes = {
        "1": idle_mode_1,
        "2": idle_mode_2,
        "3": idle_mode_3,
        "4": idle_mode_4
    }

    print("Dostępne tryby idle:")
    for k in modes:
        print(f" {k} → idle_mode_{k}")

    selected = input("Wybierz tryb idle (1-4): ").strip()
    if selected in modes:
        print(f"Uruchamiam idle_mode_{selected} — naciśnij Ctrl+C aby przerwać")
        try:
            await modes[selected]()
        except KeyboardInterrupt:
            pixels.fill((0, 0, 0))
            pixels.show()
            print("Zakończono.")
    else:
        print("Nieprawidłowy wybór.")

if __name__ == "__main__":
    asyncio.run(main())
