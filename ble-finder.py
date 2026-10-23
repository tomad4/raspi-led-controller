import asyncio
from bleak import BleakScanner

async def main():
    print("Skanuję urządzenia BLE przez 30 sekund...")
    devices = await BleakScanner.discover(timeout=30)
    for d in devices:
        print(f"Nazwa: {d.name or 'Brak nazwy'}, MAC: {d.address}, RSSI: {d.rssi}")

asyncio.run(main())
