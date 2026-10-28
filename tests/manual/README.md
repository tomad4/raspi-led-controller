# Manual hardware tools

These scripts are for one-off Raspberry Pi diagnostics and LED strip checks. They can take direct control of the GPIO LED output and are not started by the application services.

Run the relevant script from the project root with the project virtual environment. For example:

```sh
sudo /opt/led-venv/bin/python /opt/raspi-led-controller/tests/manual/test_frame_animation.py
```

Most tools require WS281x hardware. Stop the main controller service before running another script that writes to the same LED strip.
