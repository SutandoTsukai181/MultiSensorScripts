# MultiSensorScripts
Scripts for graduation project

## add_col_names.py
Add column names to dataset files
requirements: pandas, `column_names.txt`, `label_legend.txt`

inputs: Sensor data from dataset (e.g. `S1-ADL1_sensors_data.txt`)
outputs: A CSV containing column names and labels for activities (e.g. `S1-ADL1_sensors_data.txt.new.csv`)

## visualize_sensors_data.py
Graph dataset CSVs obtained from [[add_col_names.py]]
requirements: pandas, plotly, dash

inputs: Sensor data CSV file with column names
outputs: Graph presented in a web app

## visualize_arduino_sensors_data.py
Display a live graph in matplotlib using data from a serial connection
requirements: pandas, matplotlib, pyserial, mplcursors

inputs: COM port number, parameters for data to read (number of vectors, etc.)
outputs: A live graph with pause and clear buttons, in addition to a CSV file with the recorded data after the graph is closed (e.g. `arduino_output/arduino_data_areal_20240423_191857.csv`)

## transform.ipynb
Notebook with steps and explanation for transforming sensor data to be more compatible with dataset values
requirements: pandas, mathutils (use [fake-bpy-module](https://github.com/nutti/fake-bpy-module/releases) to get code completions in VS Code)

inputs: CSV file saved from [[visualize_arduino_sensors_data.py]], dataset CSV from [[add_col_names.py]], column names to use, and interval details (e.g. which period to use for sampling the average)
outputs: transformed data (e.g. `arduino_data_worldacc_20240502_072215_rotated_translated.csv`)
