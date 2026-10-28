# LED Frame Controller — Raspberry Pi Zero 2 W

This project controls a 212-pixel WS281x strip, reads data from BLE devices, and provides a lightweight web control panel.

## Hardware and LED range

- Raspberry Pi Zero 2 W running Raspberry Pi OS
- 212-pixel WS281x strip; data line connected to GPIO 18
- The frame uses LEDs **9–212**. LEDs 1–8 are outside the frame and are left untouched by the main controller.
- GPIO, pixel order, brightness, active range, and frame segments are configured in settings/strip.json.
- Heart-rate device profiles and optional BLE addresses are configured in settings/connections.json.
- Power mode scans for the Cycling Power or Fitness Machine Service (FTMS) BLE profile.

Use a power supply sized for the strip's current draw. Connect the strip's ground to Raspberry Pi ground. Do not power a 212-pixel strip from a Raspberry Pi GPIO pin.

## Install the controller on Raspberry Pi

Create the project directory and copy the repository contents there:

~~~sh
sudo install -d /opt/raspi-led-controller
~~~

For a new installation, copy the project to /opt/raspi-led-controller and run the installer. It installs system packages and Python dependencies, configures the available watchdog, installs both systemd units, and enables and starts the LED controller and web panel:

~~~sh
sudo /opt/raspi-led-controller/install/install.sh
~~~

For later deployments, run the installer from the updated project checkout with `-update`. It copies only new or changed project files to /opt/raspi-led-controller, updates Python dependencies only when requirements-rpi.txt changed, reloads systemd only when a service unit changed, and restarts both services:

~~~sh
sudo ./install/install.sh -update
~~~

The update mode expects the initial installation to exist and `rsync` to be installed. It does not remove files from the Raspberry Pi.

## Device settings

Edit settings/strip.json to configure the strip length, GPIO pin, pixel order, brightness, active LED range, and named frame segments. LED ranges are one-based and inclusive. Empty side segments can be filled in once their physical LED ranges are mapped. The controller uses the configured top segment for its waiting and running-light animations.

Copy settings/connections.example.json to settings/connections.json and add the device addresses or advertised name patterns for your BLE sensors. The local connections.json is excluded from Git. If it is absent, the example profiles are used. The web panel builds its device selector from the profiles returned by the controller.

BLE addresses are not authentication credentials, but you can encrypt this settings file with Fernet. The cryptography dependency is installed with the Raspberry Pi requirements. Generate a key outside the project, encrypt the settings, and remove the plaintext file:

~~~sh
sudo /opt/led-venv/bin/python /opt/raspi-led-controller/settings/encrypt_connections.py \
  --generate-key /etc/raspi-led-controller/connections.key --remove-plaintext
~~~

The controller reads the encrypted file at startup using LED_CONNECTIONS_KEY_FILE from its systemd unit. The key file is restricted to root. To protect against someone who can read the whole SD card, keep the key outside that card and provide it securely at service startup; encryption with the key on the same disk protects the project copy from casual disclosure, not full-disk access.

The units in install/ assume these paths. The LED controller runs as root, which is required for GPIO/WS281x access. The web panel runs as the unprivileged www-data user.

Both services start at boot. To check their status and logs:

~~~sh
sudo systemctl status led-212.service led-web.service
sudo journalctl -u led-212.service -u led-web.service -f
sudo tail -F /var/log/raspi-led-controller/led-212.log /var/log/raspi-led-web/led-web.log
~~~

Both services report a systemd watchdog heartbeat. If a service process stops responding, systemd restarts it. The installer also enables the Raspberry Pi hardware watchdog when the `bcm2835_wdt` device is available; this can reboot the Pi if systemd itself stops responding. A watchdog reboot interrupts the current lighting mode and BLE connection.

Python application logs are stored separately under /var/log and rotated hourly. Rotated files older than 24 hours are removed. The journal continues to contain systemd service start, stop, and failure messages.

After changing the LED controller, restart it. The web service is restarted with it:

~~~sh
sudo systemctl restart led-212.service
~~~

The controller exposes its local API on 127.0.0.1:8765. The web panel proxies requests to it; the API itself is not exposed directly to the network.

## Web panel

The panel is static and does not require Node.js or npm. The led-web.service unit starts its server automatically. To restart the panel after changing its files:

~~~sh
sudo systemctl restart led-web.service
~~~

The panel also has a **Restart SSH** button. The installer grants `www-data` permission to run only `systemctl restart ssh.service`; it does not grant general administrative access. Deploy the update with the usual installer command to install this rule.

Get the Raspberry Pi address with hostname -I, then open this address on a phone connected to the same network:

~~~text
http://RASPBERRY-PI-IP-ADDRESS:8000
~~~

Stop a manually started server with Ctrl+C. The web panel has no login, so use it on a trusted local network.

## Panel modes

- **0 — On/Off:** turns off the active LED range or resumes the last selected mode.
- **1 — Heart Rate:** displays the heart-rate zone from the BLE chest strap.
- **2 — Power:** reads instantaneous power over BLE Cycling Power or FTMS. The color transitions from blue at 100 W to red at 300 W; values outside this range are clamped to the ends of the scale.
- **3 — Demo:** cycles through a few colors.
- **4 — Night Light:** steady, dimmable color selected in the panel, with brightness from 1% to 25%.
- **5 — Running Light:** moves a short white segment from left to right across the upper frame LEDs 112–151.

When HR or Power mode is waiting for a measurement, a three-LED runner moves along the upper edge (LEDs 112–151) and bounces between its ends. The HR runner is red; the Power runner is blue. The HR selector lists the profiles configured in settings/connections.json.

For a Garmin watch, enable heart-rate broadcasting over Bluetooth in the watch settings; ANT+-only broadcasting cannot be received by this BLE controller. Compatibility depends on the Forerunner model.

Power mode requires a trainer or power meter that exposes the standard BLE Cycling Power profile (0x1818) or FTMS (0x1826). The HRM Belt provides heart rate, not power. Night Light is a steady dim light; it does not analyze or mirror a TV picture.

## Project layout

- led-212.py — LED controller, BLE connections, and local API
- settings/strip.json — hardware configuration and LED segment geometry
- settings/connections.example.json — sample BLE profiles; local settings may be encrypted
- app_logging.py — hourly application log rotation with a 24-hour retention limit
- web/ — static panel and lightweight API proxy server
- install/install.sh — first-time installer and incremental updater
- install/led-212.service and install/led-web.service — systemd unit definitions
- requirements-rpi.txt — Python dependencies for Raspberry Pi
- tests/manual/ — hardware test and diagnostic scripts; run only when needed
- archive/ — old controller backups and unused web UI prototype
- rpi_ws281x/ — low-level library source and tools
