import sys
import time
import pexpect
import struct
import csv
import random
import sys
import asyncio
from bluez_peripheral.gatt.service import Service, ServiceCollection
from bluez_peripheral.gatt.characteristic import characteristic, CharacteristicFlags as CharFlags
from bluez_peripheral.gatt.descriptor import descriptor, DescriptorFlags as DescFlags
from bluez_peripheral.util import *
from bluez_peripheral.advert import Advertisement
from bluez_peripheral.util import Adapter
from bluez_peripheral.agent import NoIoAgent

from bluepy import btle

import simplepyble
import msgpack

def read_values(service3):
    sensor_val_char = service3.getCharacteristics("beb5483e-36e1-4688-b7f5-ea07361b26a8")[0]
    sensor_val = sensor_val_char.read()
    #sensor_val = decimal_exponent_two(sensor_val)
    print(f"values : {sensor_val} ")
    return sensor_val

def byte_array_to_int(value):
    value = bytearray(value)
    value = int.from_bytes(value, byteorder='little')
    return value


#CONNECT TO ESP32
#----------------------------------------------------------------------------
# gatt1_ESP = pexpect.spawn("sudo gatttool -b 08:D1:F9:DF:D7:BA -I")                            
# gatt1_ESP.sendline("connect")
# gatt1_ESP.expect("Connection successful")

# gatt2_ESP = pexpect.spawn("sudo gatttool -b 08:D1:F9:C7:14:DE -I")
# gatt2_ESP.sendline("connect")
# gatt2_ESP.expect("Connection successful")

# gatt3_NRF = pexpect.spawn("sudo gatttool -b 4D:C8:D6:CF:45:50 -I")
# gatt3_NRF.sendline("connect")
# gatt3_NRF.expect("Connection successful")

# gatt4_NRF = pexpect.spawn("sudo gatttool -b D9:4D:33:22:7F:55 -I")
# gatt4_NRF.sendline("connect")
# gatt4_NRF.expect("Connection successful")

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


def connect_simple(address):
   global adapter
   if adapter is None:
      adapter = get_adapter()

   adapter.set_callback_on_scan_start(lambda: print("Scan started."))
   adapter.set_callback_on_scan_stop(lambda: print("Scan complete."))
   adapter.set_callback_on_scan_found(lambda peripheral: print(f"Found {peripheral.identifier()} [{peripheral.address()}]"))

   # Scan for 1.5 seconds
   adapter.scan_for(1500)
   peripherals = adapter.scan_get_results()

   p = [per for per in peripherals if per.address() == address]

   if len(p) == 0:
      print(f'Could not find peripheral with address {address}')
      return None
   
   print(f'Found peripheral {address}')
   p[0].connect()
   print(f'Successfully connected!')

   return p[0]



#--------------------------------------------------------
# CONNECT WITH BLUEPY
# RIGHT ARM
def data_1():
    mac_adrs3 = '08:D1:F9:DF:D7:BA'
    
    print("Connecting..")
    tp3_sense = btle.Peripheral(mac_adrs3,"random")
    
    print("Discovering Services..")
    _=tp3_sense.services
    tire3_sensing_service = tp3_sense.getServiceByUUID("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
    
    print("Discovering characteristics..")
    _= tire3_sensing_service.getCharacteristics()
    
    return tire3_sensing_service
# LEFT ARM
def data_2():
    mac_adrs3 = '08:D1:F9:C7:14:DE'
    
    print("Connecting..")
    tp3_sense = btle.Peripheral(mac_adrs3,"random")
    
    print("Discovering Services..")
    _=tp3_sense.services
    tire3_sensing_service = tp3_sense.getServiceByUUID("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
    
    print("Discovering characteristics..")
    _= tire3_sensing_service.getCharacteristics()
    
    return tire3_sensing_service
# LEFT LEG
def data_3():
    mac_adrs3 = 'CD:C8:D6:CF:45:50'
    
    print("Connecting..")
    tp3_sense = btle.Peripheral(mac_adrs3)
    
    print("Discovering Services..")
    _=tp3_sense.services
    tire3_sensing_service = tp3_sense.getServiceByUUID("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
    
    print("Discovering characteristics..")
    _= tire3_sensing_service.getCharacteristics()
    
    return tire3_sensing_service
# RIGHT LEG
def data_4():
    mac_adrs3 = 'D9:4D:33:22:7F:55'
    
    print("Connecting..")
    tp3_sense = btle.Peripheral(mac_adrs3,"random")
    
    print("Discovering Services..")
    _=tp3_sense.services
    tire3_sensing_service = tp3_sense.getServiceByUUID("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
    
    print("Discovering characteristics..")
    _= tire3_sensing_service.getCharacteristics()
    
    return tire3_sensing_service

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
      return bytes(self._some_value, "utf-8")

   # This is a write only characteristic.
   @characteristic("BEF1", CharFlags.WRITE)
   def my_writeonly_characteristic(self, options):
      # This function is a placeholder.
      # In Python 3.9+ you don't need this function (See PEP 614)
      pass

   # In Python 3.9+:
   # 
   # Define a characteristic writing function like so.
   #@my_readonly_characteristic.setter
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

# This needs running in an awaitable context.
async def main():
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

   
   my_service_ids = ["3206"] # The services that we're advertising.
   my_appearance = 0x0340 # The appearance of my service.
   # See https://specificationrefs.bluetooth.com/assigned-values/Appearance%20Values.pdf
   my_timeout = 600 # Advert should last 60 seconds before ending (assuming other local
   # services aren't being advertised).
   advert = Advertisement("Raspi5School", my_service_ids, my_appearance, my_timeout)
   await advert.register(bus, adapter)
#    time.sleep(10)
   num=0
   # d1 = data_1()
   # d2 = data_2()

   # d3 = data_3()
   # d4 = data_4()

   p1 = connect_simple('08:D1:F9:C7:14:DE')

   while True:
        # Update the heart rate.
      #   gatt1_ESP.sendline("char-read-hnd 002a")
      #   gatt1_ESP.expect("Characteristic value/descriptor: .*")
      #   values1 = str(bytes.fromhex(gatt1_ESP.after.decode("utf-8")[32:-39]))[2:-1] #TODO change to msgpaack
      #   print(f"Values1: {values1}")
      #   service.update_value(values1)
        
      #   gatt2_ESP.sendline("char-read-hnd 002a")
      #   gatt2_ESP.expect("Characteristic value/descriptor: .*")
      #   values2 = str(bytes.fromhex(gatt2_ESP.after.decode("utf-8")[32:-39]))[2:-1] #TODO change to msgpaack
      #   print(f"Values2: {values2}")
      #   service.update_value(values2)

      #   gatt3_NRF.sendline("char-read-hnd 000c") #TODO check for the correct handle value
      #   gatt3_NRF.expect("Characteristic value/descriptor: .*")
      #   values3 = str(bytes.fromhex(gatt3_NRF.after.decode("utf-8")[32:-39]))[2:-1] #TODO change to msgpaack
      #   print(f"Values3: {values3}")
      #   service.update_value(values3)

      #   gatt4_NRF.sendline("char-read-hnd 000c") #TODO check for the correct handle value
      #   gatt4_NRF.expect("Characteristic value/descriptor: .*")
      #   values4 = str(bytes.fromhex(gatt4_NRF.after.decode("utf-8")[32:-39]))[2:-1] #TODO change to msgpaack
      #   print(f"Values4: {values4}")


      contents = p1.read(service_uuid, characteristic_uuid)

      if len(contents) != 0:
         unpacked = msgpack.unpackb(contents)
         
         print(unpacked)

      # value1 =  read_values(d1)
      # value2 =  read_values(d2)
      # value3 =  read_values(d3)
      
      # value4 =  read_values(d4)

      # values = value1 + value2 + value3 + value4
      # value3 = "helloo"

      # service.update_value(str(value1))

      # Handle dbus requests.
      await asyncio.sleep(0.5) 
   # Wait for the service to disconnect.
   await bus.wait_for_disconnect()

if __name__ == "__main__":
    asyncio.run(main())
