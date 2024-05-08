import simplepyble
import msgpack
import time

DEVICES = [
    '08:d1:f9:c7:14:de', # ESP32 DevkitC v4 1
    # '08:d1:f9:df:d7:ba', # ESP32 DevkitC v4 2
    'cd:c8:d6:cf:45:50', # XIAO 1
]

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
            if(characteristic.uuid() == "beb5483e-36e1-4688-b7f5-ea07361b26a8"):
                print(f"Service: {service.uuid()}")
                print(f"Characteristic: {characteristic.uuid()}")
                service_uuid=service.uuid() 
                characteristic_uuid=characteristic.uuid()

    # Query the user to pick a service/characteristic pair
    # print("Please select a service/characteristic pair:")
    # for i, (service_uuid, characteristic) in enumerate(service_characteristic_pair):
    #     print(f"{i}: {service_uuid} {characteristic}")

    # choice = int(input("Enter choice: "))

    # Write the content to the characteristic0

    
    prev_time = 0
    while(True):
        try:
            contents = peripheral.read(service_uuid, characteristic_uuid)
            
            # print(contents)
            
            if len(contents) != 0:
                unpacked = msgpack.unpackb(contents)
                
                if ('timestamp' in unpacked and unpacked['timestamp'] != prev_time):
                    prev_time = unpacked['timestamp']
                    print(unpacked)
            
            # contentString = contents.decode("utf-8")
            # contentArray = contentString.split(",")
            # mpu1 = contentArray[0:16]
            # mpu2 = contentArray[16:]
            # #QW,QX,QY,QZ,EuX,EuY,EuZ,AccRealX,AccRealY,AccRealZ,AccX,AccY,AccZ,GyroX,GyroY,GyroZ
            # print("MPU-1")
            # print(f"Quat:     {mpu1[0]}\t{mpu1[1]}\t{mpu1[2]}\t{mpu1[3]}")
            # print(f"EuX:      {mpu1[4]}\t{mpu1[5]}\t{mpu1[6]}")
            # print(f"AccRealX: {mpu1[7]}\t{mpu1[8]}\t{mpu1[9]}")
            # print(f"AccX:     {mpu1[10]}\t{mpu1[11]}\t{mpu1[12]}")
            # print(f"GyroX:    {mpu1[13]}\t{mpu1[14]}\t{mpu1[15]}")
            # print("===============================================")
            # print("MPU-2")
            # print(f"Quat:     {mpu2[0]}\t{mpu2[1]}\t{mpu2[2]}\t{mpu2[3]}")
            # print(f"EuX:      {mpu2[4]}\t{mpu2[5]}\t{mpu2[6]}")
            # print(f"AccRealX: {mpu2[7]}\t{mpu2[8]}\t{mpu2[9]}")
            # print(f"AccX:     {mpu2[10]}\t{mpu2[11]}\t{mpu2[12]}")
            # print(f"GyroX:    {mpu2[13]}\t{mpu2[14]}\t{mpu2[15]}")
            # print("===============================================")
            #print(f"Contents: {contentString}")

            time.sleep(0.5)
        except Exception as e:
            print(e)
            pass
    peripheral.disconnect()
