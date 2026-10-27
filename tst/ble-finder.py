import asyncio
from bleak import BleakScanner

async def main():
    print("Skanuję urządzenia BLE przez 30 sekund...")
    devices = await BleakScanner.discover(timeout=30, return_adv=True)
    for device, advertisement in devices.values():
        print(
            f"Nazwa: {device.name or 'Brak nazwy'}, "
            f"Identyfikator: {device.address}, RSSI: {advertisement.rssi} dBm"
        )

asyncio.run(main())
