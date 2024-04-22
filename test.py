import pandas as pd
import serial
import time

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style

df = pd.DataFrame(columns=['Quat W', 'Quat X', 'Quat Y', 'Quat Z'])
df.index.name = "1 SECOND"

# Initialize serial connection
ser = serial.Serial('COM5', 9600)
time.sleep(2)
ser.write(b'g')
time.sleep(2)

time_var = 0

fig = plt.figure()
ax = fig.add_subplot(1,1,1)

def animate(i):
    global df, ax, time_var
    
    # Read data from serial port
    ser.write(b'g')
    time.sleep(1)
    text = ser.read_until().decode('ascii')
    print(f'text: {text}')

    # Split the text into a list of integers
    try:
        vals = [int(x) for x in text.split(',')]
        
        if (len(vals) == 4):
            # print(vals)
            df.loc[time_var] = vals

            # Keep last 30 seconds
            df = df.tail(90)

            time_var += 0.3
    except:
        pass
    
    ax.clear()                                          # Clear last data frame
    ax.plot(df)                                   # Plot new data frame
    
    # ax.set_ylim([0, 1200])                              # Set Y axis limit of plot
    ax.set_title("Arduino Data")                        # Set title of figure
    ax.set_ylabel("Value")                              # Set title of y axis 
    


def main():
    ani = animation.FuncAnimation(fig, animate, interval=1000)
    plt.show()
    
    # while True:
    #     # Read data from serial port
    #     ser.write(b'g')
    #     time.sleep(1)
    #     text = ser.read_until().decode('ascii')
    #     print(f'text: {text}')

    #     # # Split the text into a list of integers
    #     # try:
    #     #     vals = [int(x) for x in text.split(',')]
            
    #     #     if (len(vals) == 4):
    #     #         # print(vals)
    #     #         df.loc[time_var] = vals

    #     #         # Keep last 30 seconds
    #     #         df = df.tail(90)

    #     #         time_var += 0.3
    #     # except:
    #     #     pass
        
        


if __name__ == "__main__":
    main()
