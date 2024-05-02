import pandas as pd
import serial
import time
import os

import matplotlib.pyplot as plt
import matplotlib.animation as animation

from matplotlib.widgets import Button

import mplcursors
import datetime

# Index of vector to be plotted
VECTOR_TO_PLOT = 0

# Number of vectors to read from serial port (example: World Acceleration, Gravity)
VECTOR_COUNT = 1

# Length of vector (example: x, y, z)
VECTOR_SIZE = 3

dfs = []
for i in range(VECTOR_COUNT):
    dfs.append(pd.DataFrame(columns=[f"Axis {i}" for i in range(VECTOR_SIZE)]))
    dfs[i].index.name = "1 SECOND"

# Initialize serial connection
ser = serial.Serial("COM4", 115200, timeout=0.066)
time.sleep(2)
ser.write(b"g")
time.sleep(1)

time_var = 0

fig, ax = plt.subplots()
fig.subplots_adjust(bottom=0.2)

axclear = fig.add_axes([0.66, 0.03, 0.1, 0.07])
bclear = Button(axclear, "Clear")

axpause = fig.add_axes([0.78, 0.03, 0.1, 0.07])
bpause = Button(axpause, "Pause")

anim = None
anim_running = True


def onClickClear(event):
    global ax, dfs, time_var
    for i in range(len(dfs)):
        dfs[i] = dfs[i].iloc[0:0]

    time_var = 0

    ax.clear()
    fig.canvas.draw()


def onClickPause(event):
    global anim_running, bpause
    if anim_running:
        anim.pause()
        anim_running = False
        bpause.label.set_visible(False)
        bpause.label2.set_visible(True)
    else:
        anim.resume()
        anim_running = True
        bpause.label.set_visible(True)
        bpause.label2.set_visible(False)


def animate(i):
    global dfs, ax, time_var

    # Read data from serial port
    ser.write(b"g")
    # time.sleep(0.05)

    data = []
    for i in range(VECTOR_COUNT):
        text = ser.read_until().decode("ascii").strip()
        data.append(text)
        # print(f"text: \t{text}")

    # Split the text into a list of integers
    try:
        for i in range(VECTOR_COUNT):
            if len(data[i]) == 0:
                continue

            vals = [float(x) for x in data[i].split("\t")]

            if len(vals) == VECTOR_SIZE:
                dfs[i].loc[time_var] = vals

                # Keep last 15 seconds
                dfs[i] = dfs[i].tail(1500)

        time_var += 0.033
    except Exception as e:
        print(f"Error in data: {data}")
        print(e)
        print()
        pass

    ax.clear()  # Clear last data frame
    lines = ax.plot(dfs[VECTOR_TO_PLOT])  # Plot new data frame
    ax.grid()

    ax.set_title("Arduino Data")  # Set title of figure
    ax.set_ylabel("Value")  # Set title of y axis

    return lines


def main():
    global anim, ax
    anim = animation.FuncAnimation(fig, animate, interval=33, cache_frame_data=False)

    mplcursors.cursor(hover=True)

    bclear.on_clicked(onClickClear)

    bpause.on_clicked(onClickPause)
    bpause.label2 = axpause.text(
        0.5, 0.5, "Resume", verticalalignment="center", horizontalalignment="center", transform=axpause.transAxes
    )
    bpause.label2.set_visible(False)

    plt.show()

    # Ensure output directory is created
    os.makedirs("arduino_output", exist_ok=True)

    # Save dataframes to csv after plot is closed
    for i in range(VECTOR_COUNT):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dfs[i].to_csv(os.path.join("arduino_output", f"arduino_data_{i}_{timestamp}.csv"))


if __name__ == "__main__":
    main()
