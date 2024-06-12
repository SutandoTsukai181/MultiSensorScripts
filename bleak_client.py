import asyncio
import concurrent.futures
import datetime
from enum import IntEnum
import json
import logging
import time
from collections import deque
from typing import Optional
import subprocess

from bluez_peripheral.gatt.service import Service
from bluez_peripheral.gatt.characteristic import characteristic, CharacteristicFlags as CharFlags
from bluez_peripheral.util import Adapter, get_message_bus
from bluez_peripheral.advert import Advertisement
from bluez_peripheral.agent import NoIoAgent

import colorlog
import msgpack
import lz4.frame
from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic

from debug_helper import get_data_cycle
JSON_DATA_CYCLE = get_data_cycle()

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

DEVICES = [
    "08:D1:F9:C7:14:DE",  # ESP32 DevkitC v4 1 (Left arm)
    "08:D1:F9:DF:D7:BA",  # ESP32 DevkitC v4 2 (Right arm)
    "CD:C8:D6:CF:45:50",  # XIAO 1 (Left leg)
    "D9:4D:33:22:7F:55",  # XIAO 2 (Right leg)
]

DEVICE_NAMES = [
    "LEFT_ARM",
    "RIGHT_ARM",
    "LEFT_LEG",
    "RIGHT_LEG",
]

DEVICE_SHORT_NAMES = [''.join([x[0] for x in dn.split('_')]) for dn in DEVICE_NAMES]

class NodeStatus(IntEnum):
    UNAVAILABLE = 0  # Device was not found at the start
    CONNECTED = 1
    DISCONNECTED = 2
    RECONNECTING = 3

class TimedQueue:
    def __init__(self, time_threshold):
        self.threshold = time_threshold
        self.queue = deque()

    def put(self, value):
        now = time.time()
        self.queue.append((now, value))
        self.discard_old_values(now)

    def discard_old_values(self, now=None):
        if now is None:
            now = time.time()

        cutoff_time = now - self.threshold
        try:
            while self.queue[0][0] < cutoff_time:
                # Remove older values from the queue
                self.queue.popleft()
        except IndexError:
            pass

    def get(self):
        # User should check for empty/qsize before calling this
        return self.queue.popleft()

    def get_front(self):
        # User should check for empty/qsize before calling this
        return self.queue.pop()

    def empty(self):
        self.discard_old_values()
        return len(self.queue) == 0

    def qsize(self):
        self.discard_old_values()
        return len(self.queue)

    def clear(self):
        self.queue.clear()

class CentralService(Service):
    def __init__(self):
        super().__init__(SERVICE_UUID, True)

    @characteristic(CHARACTERISTIC_UUID, CharFlags.NOTIFY)
    def combined_data(self, options): ...

    def update_combined_data(self, data):
        """Note that notification is asynchronous (you must await something at some point after calling this)."""
        self.combined_data.changed(data)


DATA_VALIDITY_THRESHOLD = 0.300

bleak_clients: list[Optional[BleakClient]] = [None] * len(DEVICES)
client_statuses = [NodeStatus.UNAVAILABLE] * len(DEVICES)

notification_queues = [TimedQueue(DATA_VALIDITY_THRESHOLD) for _ in DEVICES]

# Setup logging
LOG_FORMAT = "%(log_color)s%(asctime)-15s %(name)-8s %(levelname)s: %(message)s"

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(LOG_FORMAT))

logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def handle_notification(
    index: int, characteristic: BleakGATTCharacteristic, data: bytearray
):
    notification_queues[index].put(data)

    # logger.info(f"Notified by {DEVICE_NAMES[index]}: {data.hex()}")
    # logger.info(f"Notified by {DEVICE_NAMES[index]}. Queue size: {notification_queues[index].qsize()}")


def thread_callback(callback, *args):
    # This function runs the callback in a separate thread
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, callback, *args)


def disconnect_client(index: int, client: BleakClient):
    logger.error(f"Disconnected from {DEVICE_NAMES[index]}")
    bleak_clients[index] = None
    client_statuses[index] = NodeStatus.DISCONNECTED


CONNECTION_TIMEOUT = 8


async def add_client(index: int, device: BLEDevice):
    client = BleakClient(
        device, disconnected_callback=lambda bc: disconnect_client(index, bc)
    )

    try:
        # Connection can bug out sometimes
        async with asyncio.timeout(CONNECTION_TIMEOUT):
            await client.connect()

        logger.info(f"Successfully connected to {DEVICE_NAMES[index]}")

        # Force discover the services (otherwise characteristic might not be found)
        _ = await client.get_services()
        # for s in services:
        #     print(f'\nService: {s.uuid}')
        #     for c in s.characteristics:
        #         print(f'Characteristic: {c.uuid}')

        # Handle notifications in a separate thread for each client
        await client.start_notify(
            CHARACTERISTIC_UUID,
            callback=lambda ch, d: thread_callback(handle_notification, index, ch, d),
        )

        # Add the client to the list
        bleak_clients[index] = client
        client_statuses[index] = NodeStatus.CONNECTED
    except TimeoutError:
        logger.error(f"Connection to {DEVICE_NAMES[index]} timed out")
        await client.disconnect()
        return
    except Exception as e:
        logger.error(f"Error connecting to {DEVICE_NAMES[index]}: {e}")
        await client.disconnect()
        return


def restart_bluetooth():
    subprocess.call(["bluetoothctl", "power", "off"])
    time.sleep(0.2)
    subprocess.call(["bluetoothctl", "power", "on"])
    time.sleep(0.3)


def disconnect_all():
    for i, client in enumerate(bleak_clients):
        if client is not None:
            disconnect_client(i, client)


# Scan parameters
SCAN_TIMEOUT = 1.5
SCAN_CHECK_INTERVAL = 0.5

# Global flag to avoid creating multiple scanners
is_scanning = False


async def check_and_reconnect():
    global is_scanning

    indices = [i for i in range(len(bleak_clients)) if bleak_clients[i] is None]
    addresses = [DEVICES[i] for i in indices]

    if len(indices) == 0:
        return

    logger.info(f"Scanning for {[DEVICE_NAMES[i] for i in indices]}...")

    scanned_devices = dict()

    async with BleakScanner() as scanner:
        try:
            is_scanning = True
            async with asyncio.timeout(SCAN_TIMEOUT):
                while True:
                    for bd in scanner.discovered_devices:
                        print((bd.name, bd.address))
                        if bd.address in addresses:
                            scanned_devices[bd.address] = bd
                            client_statuses[indices[addresses.index(bd.address)]] = NodeStatus.RECONNECTING

                            # Stop once we find all addresses
                            if len(scanned_devices) == len(addresses):
                                break

                    await asyncio.sleep(SCAN_CHECK_INTERVAL)
        except TimeoutError:
            pass

    is_scanning = False

    for bd in scanned_devices.values():
        await asyncio.sleep(0.3)  # Sleep for a while before connecting
        logger.info(f"Connecting to {bd.name} at {bd.address}")
        await add_client(indices[addresses.index(bd.address)], bd)


# Intervals in seconds
MAIN_LOOP_INTERVAL = 0.120
MAX_MCU_TIME_DIFFERENCE = 0.150

MAX_CONSECUTIVE_FAIL = 15
consecutive_empty_packet_count = 0


def combine_data_and_send() -> Optional[dict]:
    global consecutive_empty_packet_count

    while True:
        # Get the latest notification from each queue
        latest_notifications: list[Optional[tuple[float, bytearray]]] = [
            q.get() if not q.empty() else None for q in notification_queues
        ]

        if any(n is None for n in latest_notifications):
            logger.warning(f"Skipping combined packet due to empty queues: {[DEVICE_NAMES[i] for i, n in enumerate(latest_notifications) if n is None]}")
            consecutive_empty_packet_count += 1

            if consecutive_empty_packet_count > MAX_CONSECUTIVE_FAIL:
                consecutive_empty_packet_count = 0

                # If all devices appear to be connected, disconnect all of them to force scanning
                if not any([bc for bc in bleak_clients if bc is None]):
                    disconnect_all()
                    restart_bluetooth()
            return

        consecutive_empty_packet_count = 0

        # Calculate the time difference between the latest notifications
        time_diff = max(n[0] for n in latest_notifications) - min(
            n[0] for n in latest_notifications
        )

        # While the time difference is greater than the threshold, drop older values from the queue with the oldest
        if time_diff > MAX_MCU_TIME_DIFFERENCE:
            # logger.warning(f"Skipping oldest packet due to time difference between MCUs ({int(time_diff * 1000)}ms)")

            # Find the queue with the oldest data
            min_queue = notification_queues[
                latest_notifications.index(
                    min(latest_notifications, key=lambda n: n[0])
                )
            ]

            # Remove the oldest notification
            if not min_queue.empty():
                min_queue.get()

            continue
        else:
            # Combine the data from the notifications
            last_i = 0
            try:
                combined_data = dict()
                combined_data["t"] = time.time()

                for i, n in enumerate(latest_notifications):
                    last_i = i
                    combined_data[DEVICE_SHORT_NAMES[i]] = dict()
                    combined_data[DEVICE_SHORT_NAMES[i]]["d"] = msgpack.unpackb(n[1])
                    combined_data[DEVICE_SHORT_NAMES[i]]["s"] = int(client_statuses[i])
                    # combined_data[DEVICE_SHORT_NAMES[i]]["data"] = json.loads(n[1].decode())

                return combined_data
            except Exception as e:
                logger.error(f"Error unpacking data from {DEVICE_NAMES[last_i]}: {e}")
                print(f"Received data:\n{latest_notifications[last_i][1]}")
                # print(f'Received data:\n{latest_notifications[last_i][1].decode()}')
                return


def save_file(data):
    fname = f"/home/raspiserver/Desktop/test_data_06_06/{datetime.datetime.now()}.json"

    try:
        with open(fname, "w") as f:
            json.dump({"data": data}, f)

        logger.info(f"************** Saved {fname} **************\n")
    except Exception as e:
        logger.error(f'Error saving file "{fname}": {e}')


async def main():
    # Alternativly you can request this bus directly from dbus_next.
    bus = await get_message_bus()

    # Create the service and register it
    central_service = CentralService()
    await central_service.register(bus)

    # An agent is required to handle pairing 
    agent = NoIoAgent()
    # This script needs superuser for this to work. (not really)
    await agent.register(bus)

    adapter = await Adapter.get_first(bus)

    # Start an advert that will last forever.
    advert = Advertisement("CENTRAL_PI", [SERVICE_UUID], 0, timeout=0)
    await advert.register(bus, adapter)

    count = 0
    data = []

    while True:
        try:
            combined_data = combine_data_and_send()
            # combined_data = next(JSON_DATA_CYCLE)

            if combined_data:
                # Send combined data to server Pi
                # Note that after calling the update function, the data will not be sent until an await occurs
                combined_data_packed = msgpack.packb(combined_data)
                combined_data_compressed = lz4.frame.compress(combined_data_packed, compression_level=lz4.frame.COMPRESSIONLEVEL_MINHC + 5)
                central_service.update_combined_data(combined_data_compressed)

                if len(combined_data_compressed) >= 512:
                    logger.error(f"Combined data size ({len(combined_data_compressed)} bytes) exceeds 512 bytes")

                # Only add the data if it's not None
                data.append(combined_data)
                if count % 10 == 0:
                    logger.info(f"Combined data ({len(combined_data_compressed)} bytes): {combined_data}\n\n")
                    # logger.info(f"Combined data packed: {combined_data_packed}\n\n")

            count += 1

            # Save every 10 items or 20 iterations
            # This ensures that the last data is saved even if it's less than 10 items
            if len(data) >= 10 or (count >= 20 and len(data) > 0):
                count = 0
                # save_file(data)
                data.clear()

            # The script will crash on Linux if we create two instances of BleakScanner
            if not is_scanning:
                await check_and_reconnect()

            # Sleep for a while before checking again
            await asyncio.sleep(MAIN_LOOP_INTERVAL)
        except Exception as e:
            logger.error(f"Error in main loop: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        disconnect_all()
        logger.info("Disconnected all devices")
    except BaseException as e:
        disconnect_all()

        raise e
