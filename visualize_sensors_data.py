import itertools
import sys

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html

acc_list = [
    "RKN^",
    "HIP",
    "LUA^",
    "RUA_",
    "LH",
    "BACK",
    "RKN_",
    "RWR",
    "RUA^",
    "LUA_",
    "LWR",
    "RH",
]

imu_list = [
    "BACK",
    "RUA",
    "RLA",
    "LUA",
    "LLA",
]

imu_shoe_list = [
    "L-SHOE",
    "R-SHOE",
]

column_list = (
    [f"Acc {acc}" for acc in acc_list]
    + list(
        itertools.chain(
            *[[f"IMU {imu} acc", f"IMU {imu} gyro", f"IMU {imu} magnetic", f"IMU {imu} Quaternion"] for imu in imu_list]
        )
    )
    + list(
        itertools.chain(
            *[
                [
                    f"IMU {imu} Eu",
                    f"IMU {imu} Nav_A",
                    f"IMU {imu} Body_A",
                    f"IMU {imu} AngVelBodyFrame",
                    f"IMU {imu} AngVelNavFrame",
                    f"IMU {imu} Compass",
                ]
                for imu in imu_shoe_list
            ]
        )
    )
)

df: pd.DataFrame = None
sensors_data_file: str = ""


@callback(
    Output("graph-content", "figure"),
    Input("dropdown-selection", "value"),
    Input("checklist-selection", "value"),
    Input("my-range-slider", "value"),
)
def update_graph_dropdown(dropdown_values, checklist_values, slider_range):
    checklist_indices = dict(map(reversed, enumerate(["X", "Y", "Z", "W"])))
    checklist_values_quat = [checklist_indices[x] for x in checklist_values]

    dff = df[
        [
            col
            for col in df.columns
            if any([val in col for val in dropdown_values])
            and (
                col.endswith(tuple(checklist_values))
                or col.endswith(tuple(["Quaternion" + str(i + 1) for i in checklist_values_quat]))
            )
        ]
    ]

    fig = px.line(
        dff.loc[slider_range[0] : slider_range[1]],
        title=sensors_data_file.split(".")[0],
        labels=dict(variable="Column Name", value="Value"),
    )
    fig.update_traces(mode="lines", hovertemplate="%{y}")
    fig.update_layout(hovermode="x unified", xaxis_title="Time (s)")

    return fig


def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_sensors_data.py FILE [SENSORS_FILE]")
        sys.exit(1)

    global df, sensors_data_file

    sensors_data_file = sys.argv[1]
    # sensors_data_file = "S1-ADL1_sensors_data.txt.new.csv"

    df = pd.read_csv(sensors_data_file)

    # Set Millisec column to index
    df.set_index(df.columns[0], inplace=True)

    # Divide by 1000 to convert from milliseconds to seconds
    df.index = df.index / 1000
    df.index.name = "1 SECOND"

    sensors_figure = []
    if len(sys.argv) == 3:
        file2 = sys.argv[2]
        df2 = pd.read_csv(file2)
        df2.set_index(df2.columns[0], inplace=True)

        df2.index.name = "1 SECOND"

        # Sensors figure
        sensor_fig = px.line(
            df2,
            title=file2.split(".")[0],
            labels=dict(variable="Column Name", value="Value"),
        )

        sensor_fig.update_traces(mode="lines", hovertemplate="%{y}")
        sensor_fig.update_layout(hovermode="x unified", xaxis_title="Time (s)")

        sensors_figure = [
            dcc.Graph(
                    figure=sensor_fig,
                    id="graph2-content",
                ),
        ]

    app = Dash(__name__, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])

    app.layout = html.Div(
        [
            dcc.Dropdown(
                column_list, ["Acc LUA^",], multi=True, id="dropdown-selection"
            ),
            dcc.Checklist(
                options={"X": "X axis", "Y": "Y axis", "Z": "Z axis", "W": "W axis"},
                value=["X", "Y", "Z", "W"],
                inline=True,
                id="checklist-selection",
            ),
            dcc.Graph(id="graph-content"),
            dcc.RangeSlider(
                min=0,
                max=df.last_valid_index(),
                step=1,
                value=[0, 600],
                marks={0: "0", df.last_valid_index(): f"{df.last_valid_index()}"},
                tooltip={"placement": "bottom", "always_visible": True},
                id="my-range-slider",
            ),
            *sensors_figure,
        ]
    )

    app.run()


if __name__ == "__main__":
    main()
