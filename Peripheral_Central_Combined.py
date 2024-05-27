import asyncio
import threading
import json
import time
import datetime

from bluez_peripheral.gatt.service import Service
from bluez_peripheral.gatt.characteristic import (
    characteristic,
    CharacteristicFlags as CharFlags,
)
from bluez_peripheral.gatt.descriptor import descriptor, DescriptorFlags as DescFlags
from bluez_peripheral.util import *
from bluez_peripheral.advert import Advertisement
from bluez_peripheral.util import Adapter
from bluez_peripheral.agent import NoIoAgent

import simplepyble
import msgpack

RECONNECTION_DELAY = 1

DEVICES = [
    "08:D1:F9:C7:14:DE",  # ESP32 DevkitC v4 1 (Left arm)
    "08:D1:F9:DF:D7:BA",  # ESP32 DevkitC v4 2 (Right arm)
    "CD:C8:D6:CF:45:50",  # XIAO 1 (Left leg)
    "D9:4D:33:22:7F:55",  # XIAO 2 (Right leg)
]

def do_every(period, f, *args):
    def g_tick():
        t = time.time()
        while True:
            t += period
            yield max(t - time.time(), 0)

    g = g_tick()
    while True:
        time.sleep(next(g))
        f(*args)


def start_thread(target, *args, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()

    return t


def start_scheduled_thread(interval, target, *args):
    return start_thread(do_every, interval, target, *args)

adapter = None


def get_adapter():
    adapters = simplepyble.Adapter.get_adapters()

    if len(adapters) == 0:
        print("No adapters found")
    elif len(adapters) == 1:
        adapter = adapters[0]
    else:
        # Query the user to pick an adapter
        print("Please select an adapter:")
        for i, adapter in enumerate(adapters):
            print(f"{i}: {adapter.identifier()} [{adapter.address()}]")

        choice = int(input("Enter choice: "))
        adapter = adapters[choice]

    print(f"Selected adapter: {adapter.identifier()} [{adapter.address()}]")

    return adapter


def connect_simple(address, peripherals=None):
    global adapter
    if adapter is None:
        adapter = get_adapter()

    adapter.set_callback_on_scan_start(lambda: print("Scan started."))
    adapter.set_callback_on_scan_stop(lambda: print("Scan complete."))
    adapter.set_callback_on_scan_found(
        lambda peripheral: print(f"Found {peripheral.identifier()} [{peripheral.address()}]")
    )

    if peripherals is None:
        # Scan for 2 seconds
        adapter.scan_for(2000)
        peripherals = adapter.scan_get_results()

    p = [per for per in peripherals if per.address() == address]

    if len(p) == 0:
        print(f"Could not find peripheral with address {address}")
        return None

    print(f"Found peripheral {p[0].identifier()}")
    p[0].connect()
    print(f"Successfully connected!")

    return p[0]


# Define a service like so.
class AllTogether(Service):
    def __init__(self):
        self._some_value = None
        # Call the super constructor to set the UUID.
        super().__init__("4fafc201-1fb5-459e-8fcc-c5c9c331914b", True)

    # Use the characteristic decorator to define your own characteristics.
    # Set the allowed access methods using the characteristic flags.
    @characteristic("beb5483e-36e1-4688-b7f5-ea07361b26a8", CharFlags.READ)
    def my_readonly_characteristic(self, options):
        # Characteristics need to return bytes.
        return bytes(self._some_value, "utf-8") if not isinstance(self._some_value, bytes) else self._some_value

    # This is a write only characteristic.
    @characteristic("BEF1", CharFlags.WRITE)
    def my_writeonly_characteristic(self, options):
        # This function is a placeholder.
        # In Python 3.9+ you don't need this function (See PEP 614)
        pass

    # In Python 3.9+:
    #
    # Define a characteristic writing function like so.
    # @my_readonly_characteristic.setter
    @characteristic("BEF1", CharFlags.WRITE).setter
    def my_writeonly_characteristic(self, value, options):
        # Your characteristics will need to handle bytes.
        self._some_value = value

    # Associate a descriptor with your characteristic like so.
    # Descriptors have largely the same flags available as characteristics.
    @descriptor("BEF2", my_readonly_characteristic, DescFlags.READ)
    # Alternatively you could write this:
    # @my_writeonly_characteristic.descriptor("BEF2", DescFlags.READ)
    def my_readonly_descriptors(self, options):
        # Descriptors also need to handle bytes.
        return bytes("This characteristic is completely pointless!", "utf-8")

    def update_value(self, new_value):
        self._some_value = new_value


service_uuid = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
characteristic_uuid = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

data = []


def save_file():
    global data
    fname = f"/home/raspiserver/Desktop/test_data/{datetime.datetime.now()}.json"
    with open(fname, "w") as f:
        json.dump({"data": data}, f)

    print(f"Saved {fname}")


# This needs running in an awaitable context.
async def main():
    global data

    # Get the message bus.
    bus = await get_message_bus()
    # Create an instance of your service.
    service = AllTogether()
    # Register the service with the message bus.
    await service.register(bus)
    # An agent is required if you wish to handle pairing.
    agent = NoIoAgent()
    # This line needs superuser for this to work.
    await agent.register(bus)
    adapter = await Adapter.get_first(bus)
    my_service_ids = ["3206"]  # The services that we're advertising.
    my_appearance = 0x0340  # The appearance of my service.
    # See https://specificationrefs.bluetooth.com/assigned-values/Appearance%20Values.pdf
    my_timeout = 600  # Advert should last 60 seconds before ending (assuming other local
    # services aren't being advertised).
    advert = Advertisement("Raspi5School", my_service_ids, my_appearance, my_timeout)
    await advert.register(bus, adapter)
    #    time.sleep(10)

    peripherals = []
    disconnected_indices = []

    def reconnect_peripheral(i):
        p = peripherals[i]
        func_name = f'[Reconnecting {p.identifier()}] '

        while True:
            try:
                p.connect()
                break
            except Exception as e2:
                print(func_name + f'Failed reconnecting: {e2}')

                try:
                    p = connect_simple(p.address())
                    
                    if p:
                        peripherals[i] = p
                        break
                    
                    print(func_name + f'Could not find address {p.address()}')
                except Exception as e3:
                    print(func_name + f'Failed rescanning: {e3}')
                    print(e3)
            
            # Wait before trying again
            time.sleep(RECONNECTION_DELAY)

        if i in disconnected_indices:
            disconnected_indices.remove(i)

    adapter.scan_for(2000)
    scanned = adapter.scan_get_results()
    for d in DEVICES:
        peripherals.append(connect_simple(d), scanned)

    print(f"Connected to {len(peripherals)} peripherals")

    # count = 0
    while True:
        combined = dict()
        for i in range(len(peripherals)):
            if i in disconnected_indices:
                continue

            p = peripherals[i]

            if p is None:
                continue

            try:
                contents = p.read(service_uuid, characteristic_uuid)

                if len(contents) != 0:
                    print(f"\nMCU: {p.identifier()}")

                    unpacked = msgpack.unpackb(contents)

                    print(unpacked)
                    combined[p.identifier()] = unpacked
            except RuntimeError as e:
                if str(e) == "Peripheral is not connected.":
                    print(f"Reconnecting {p.identifier()}")
                    
                    if i not in disconnected_indices:
                        disconnected_indices.append(i)

                    # This will keep reconnecting until it's successful
                    start_thread(reconnect_peripheral, i)
            except Exception as e:
                print(e)

        value = msgpack.packb(combined)

        print("-------------------------------")
        print(f"Combined length: {len(value)}")
        service.update_value(value)

        val = {}
        val["t"] = time.time()
        val["v"] = combined

        data.append(val)
        
        # count += 1

        # if count >= 25:
        #     count = 0
        #     save_file()
        #     data.clear()

        # Handle dbus requests.
        await asyncio.sleep(0.2)
    # Wait for the service to disconnect.
    await bus.wait_for_disconnect()


if __name__ == "__main__":
    asyncio.run(main())
