import asyncio
import concurrent.futures
import datetime
import json
import logging
import time
from typing import Optional

import colorlog
import msgpack
from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic

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


class ListQueue:
    def __init__(self, max_size=20):
        self.queue = []
        self.max_size = max_size

    def put(self, item):
        self.queue.append(item)
        if len(self.queue) > self.max_size:
            self.queue.pop(0)

    def get(self):
        return self.queue.pop(0)

    def get_front(self):
        return self.queue.pop(-1)

    def empty(self):
        return len(self.queue) == 0

    def qsize(self):
        return len(self.queue)

    def clear(self):
        self.queue.clear()

    def truncate(self, size):
        self.queue = self.queue[-size:]


MAX_QUEUE_SIZE = 20
TRUNCATED_QUEUE_SIZE = 5

bleak_clients: list[Optional[BleakClient]] = [None] * len(DEVICES)

notification_queues = [ListQueue(MAX_QUEUE_SIZE) for _ in DEVICES]

# Setup logging
LOG_FORMAT = "%(log_color)s%(asctime)-15s %(name)-8s %(levelname)s: %(message)s"
# LOG_FORMAT = "%(log_color)s%(levelname)s:%(name)s:%(message)s"

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        LOG_FORMAT,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)

logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def handle_notification(
    index: int, characteristic: BleakGATTCharacteristic, data: bytearray
):
    notification_queues[index].put((time.time(), data))

    # logger.info(f"Notified by {DEVICE_NAMES[index]}: {data.hex()}")
    # logger.info(f"Notified by {DEVICE_NAMES[index]}. Queue size: {notification_queues[index].qsize()}")


def thread_callback(callback, *args):
    # This function runs the callback in a separate thread
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, callback, *args)


def disconnect_client(index: int, client: BleakClient):
    logger.error(f"Disconnected from {DEVICE_NAMES[index]}")
    bleak_clients[index] = None


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
        services = await client.get_services()
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
    except TimeoutError:
        logger.error(f"Connection to {DEVICE_NAMES[index]} timed out")
        await client.disconnect()
        return
    except Exception as e:
        logger.error(f"Error connecting to {DEVICE_NAMES[index]}: {e}")
        await client.disconnect()
        return


# Thresholds in seconds
MAIN_LOOP_INTERVAL = 1
MAX_NOTIFICATION_INTERVAL = 0.150
DATA_VALIDITY_THRESHOLD = 0.800
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

                            # Stop once we find all addresses
                            if len(scanned_devices) == len(addresses):
                                break

                    await asyncio.sleep(SCAN_CHECK_INTERVAL)
        except TimeoutError:
            pass

    is_scanning = False

    for bd in scanned_devices.values():
        await asyncio.sleep(1)  # Sleep for a while before connecting
        logger.info(f"Connecting to {bd.name} at {bd.address}")
        await add_client(indices[addresses.index(bd.address)], bd)


def combine_data_and_send() -> Optional[dict]:
    while True:
        # Get the latest notification from each queue
        latest_notifications: list[Optional[tuple[float, bytearray]]] = [
            q.queue[-1] if not q.empty() else None for q in notification_queues
        ]

        if any(n is None for n in latest_notifications):
            logger.warning("Skipping combined packet due to empty queues")
            return

        # Calculate the time difference between the latest notifications
        time_diff = max(n[0] for n in latest_notifications) - min(
            n[0] for n in latest_notifications
        )

        # While the time difference is greater than the threshold, use older values from the queue with the latest data
        if time_diff <= MAX_NOTIFICATION_INTERVAL:
            # Combine the data from the notifications
            last_i = 0
            try:
                combined_data = dict()
                combined_data["time"] = time.time()

                for i, n in enumerate(latest_notifications):
                    last_i = i
                    combined_data[DEVICE_NAMES[i]] = msgpack.unpackb(n[1])
                    # combined_data[DEVICE_NAMES[i]] = json.loads(n[1].decode())

                # Send combined data to server Pi
                logger.info(f"Combined data: {combined_data}\n\n")

                # combined_data_packed = msgpack.packb(combined_data)

                # Remove older notifications from the queues
                for q in notification_queues:
                    if not q.empty():
                        q.truncate(TRUNCATED_QUEUE_SIZE)

                return combined_data
            except Exception as e:
                logger.error(f"Error unpacking data from {DEVICE_NAMES[last_i]}: {e}")
                print(f"Received data:\n{latest_notifications[last_i][1]}")
                # print(f'Received data:\n{latest_notifications[last_i][1].decode()}')
                return

        # Find the queue with the latest data
        max_queue = notification_queues[
            latest_notifications.index(max(latest_notifications, key=lambda n: n[0]))
        ]

        # If the current time minus the max is larger than a the data validity threshold, break the loop
        time_diff = time.time() - max_queue.queue[-1][0]
        if time_diff > DATA_VALIDITY_THRESHOLD:
            logger.warning(
                f"Skipping combined packet due to data being too old ({int(time_diff * 1000)}ms)"
            )

            # Empty all of the queues since all data is old now
            for q in notification_queues:
                if not q.empty():
                    q.clear()

            return

        # Remove the latest notification from the queue with the latest data
        max_queue.get_front()


def save_file():
    global data
    fname = f"/home/raspiserver/Desktop/test_data_06_06/{datetime.datetime.now()}.json"
    with open(fname, "w") as f:
        json.dump({"data": data}, f)

    logger.info(f"************** Saved {fname} **************\n")


async def main():
    count = 0
    data = []

    while True:
        combined_data = combine_data_and_send()

        data.append(combined_data)
        count += 1

        # Save every 5 items or 10 iterations
        if len(data) >= 5 or (count >= 10 and len(data) > 0):
            count = 0
            save_file()
            data.clear()

        # The script will crash on Linux if we create two instances of BleakScanner
        if not is_scanning:
            await check_and_reconnect()

        # Sleep for a while before checking again
        await asyncio.sleep(MAIN_LOOP_INTERVAL)  


def disconnect_all():
    for i, client in enumerate(bleak_clients):
        if client is not None:
            disconnect_client(i, client)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        disconnect_all()
        logger.info("Disconnected all devices")
    except BaseException as e:
        disconnect_all()

        raise e
