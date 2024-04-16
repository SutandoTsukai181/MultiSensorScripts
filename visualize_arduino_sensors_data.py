import itertools
import sys

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html
import serial

df = pd.DataFrame(columns=['Quat W', 'Quat X', 'Quat Y', 'Quat Z'])
df.index.name = "1 SECOND"

# Initialize serial connection
ser = serial.Serial('COM3', 115200)
# ser.write(b'g')

time = 0

@callback(
    Output("graph-content", "figure"),
    Input('interval-component', 'n_intervals'),
    Input("type-checklist-selection", "value"),
    Input("axis-checklist-selection", "value"),
)
def update_graph_dropdown(
    n,
    type_checklist_values,
    axis_checklist_values
    ):
    
    global time, df

    # Read data from serial port
    # ser.write(b'g')
    text = ser.readline().decode('ascii')

    # Split the text into a list of integers
    try:
        vals = [int(x) for x in text.split(',')]
    except:
        return

    print(vals)
    df.loc[time] = vals

    # Keep last 30 seconds
    df = df.tail(90)

    time += 0.3

    fig = px.line(
        df,
        title='MPU 6050',
        labels=dict(variable="Column Name", value="Value"),
    )
    fig.update_traces(mode="lines", hovertemplate="%{y}")
    fig.update_layout(hovermode="x unified", xaxis_title="Time (s)")

    return fig


def main():
    app = Dash(__name__, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])

    app.layout = html.Div(
        [
            dcc.Checklist(
                options={"Acc": "Acc", "Gyro": "Gyro", "Quat": "Quat", "Mag": "Mag"},
                value=["Acc", "Gyro", "Quat", "W"],
                inline=True,
                id="type-checklist-selection",
            ),
            dcc.Checklist(
                options={"X": "X axis", "Y": "Y axis", "Z": "Z axis", "W": "W axis"},
                value=["X", "Y", "Z", "W"],
                inline=True,
                id="axis-checklist-selection",
            ),
            dcc.Graph(id="graph-content"),
            dcc.Interval(
                id='interval-component',
                interval=100, # in milliseconds
                n_intervals=0
            ),
        ]
    )

    app.run(port='8051')


if __name__ == "__main__":
    main()
