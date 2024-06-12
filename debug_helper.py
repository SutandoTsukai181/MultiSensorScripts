import json
import os
from itertools import cycle

DEVICE_NAMES_MAP = {
    "LEFT_ARM": 'LA',
    "RIGHT_ARM": 'RA',
    "LEFT_LEG": 'LL',
    "RIGHT_LEG": 'RL',
}

test_folder = '../../train/stand'

# Get all files after the start file (including it)
files = os.listdir(test_folder)
files = sorted(files)

# Collect all data points into one list
json_data = []
for file in files:
    with open(os.path.join(test_folder, file), 'r') as f:
        dic = json.load(f)
        json_data.extend(dic['data'])

new_data = list()
for point in json_data:
    new_data.append({})
    for device in point:
        if device == 'time':
            new_data[-1]['t'] = point[device]
            continue

        new_data[-1][DEVICE_NAMES_MAP[device]] = {}
        new_data[-1][DEVICE_NAMES_MAP[device]]['d'] = point[device]
        new_data[-1][DEVICE_NAMES_MAP[device]]['s'] = 1
        

def get_data_cycle():
    return cycle(new_data)
