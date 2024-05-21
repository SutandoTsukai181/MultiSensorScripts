import simplepyble
import msgpack
import time

DEVICES = [
    '08:d1:f9:c7:14:de', # ESP32 DevkitC v4 1 (Left arm)
    '08:d1:f9:df:d7:ba', # ESP32 DevkitC v4 2 (Right arm)
    'cd:c8:d6:cf:45:50', # XIAO 1 (Left leg)
    'd9:4d:33:22:7f:55', # XIAO 2 (Right leg)
]

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

if __name__ == "__main__":
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

    adapter.set_callback_on_scan_start(lambda: print("Scan started."))
    adapter.set_callback_on_scan_stop(lambda: print("Scan complete."))
    adapter.set_callback_on_scan_found(lambda peripheral: print(f"Found {peripheral.identifier()} [{peripheral.address()}]"))

    # Scan for 5 seconds
    adapter.scan_for(1500)
    peripherals = adapter.scan_get_results()

    # Query the user to pick a peripheral
    print("Peripherals found:")
    peripheral = None
    for i, peripheralTemp in enumerate(peripherals):
        print(f"{i}: {peripheralTemp.identifier()} [{peripheralTemp.address()}]")
        if(peripheralTemp.address() in DEVICES):
            peripheral = peripheralTemp

    if peripheral is None:
        print("Please select a peripheral:")
        choice = int(input("Enter choice: "))
        peripheral = peripherals[choice]

    print(f"Connecting to: {peripheral.identifier()} [{peripheral.address()}]")
    peripheral.connect()

    print("Successfully connected, listing services...")
    services = peripheral.services()
    for service in services:
        for characteristic in service.characteristics():
            if(characteristic.uuid() == CHARACTERISTIC_UUID):
                print(f"Service: {service.uuid()}")
                print(f"Characteristic: {characteristic.uuid()}")
                service_uuid=service.uuid() 
                characteristic_uuid=characteristic.uuid()
    
    prev_time = 0
    while(True):
        try:
            contents = peripheral.read(service_uuid, characteristic_uuid)
            
            # print(contents)
            
            if len(contents) != 0:
                unpacked = msgpack.unpackb(contents)
                
                if ('time' in unpacked and unpacked['time'] != prev_time):
                    prev_time = unpacked['time']
                    print(unpacked)

            time.sleep(0.150)
        except Exception as e:
            print(e)
            pass
    peripheral.disconnect()
