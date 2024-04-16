import sys
import pandas as pd

COLUMN_NAMES = "column_names.txt"
LABEL_LEGEND = "label_legend.txt"


def read_column_names(lines) -> list:
    lines = [l.strip() for l in lines if l.strip() != ""]

    data_header = "Data columns:"
    label_header = "Label columns:"
    skip_length = len("Column: ")

    index_data = lines.index(data_header)
    index_label = lines.index(label_header)

    # Read the data column names
    data_names = []
    for i in range(index_data + 1, index_label):
        data_names.append(
            lines[i][skip_length:]
            .split(";")[0]
            .replace("Accelerometer", "Acc")
            .replace("InertialMeasurementUnit", "IMU")
        )

    # Read the label column names
    label_names = []
    for i in range(index_label + 1, len(lines)):
        label_names.append(lines[i][skip_length:])

    return data_names, label_names


def read_label_legend(lines) -> dict:
    # Skip the first two lines
    label_lines = lines[2:]

    tracks = {}
    for line in label_lines:
        num, track, label = [x.strip() for x in line.split("-")]
        num = int(num)

        if track not in tracks:
            tracks[track] = {}

        tracks[track][num] = label

    return tracks


def main():
    if len(sys.argv) != 2:
        print("Usage: python add_col_names.py <file>")
        sys.exit(1)

    sensors_data_file = sys.argv[1]

    with open(COLUMN_NAMES, "r") as f:
        data_names, label_names = read_column_names(f.readlines())

    with open(LABEL_LEGEND, "r") as f:
        label_tracks = read_label_legend(f.readlines())

    # Read the sensors data file
    df = pd.read_csv(sensors_data_file, sep=" ", names=(data_names + label_names), dtype="Int64")

    # Concatenate both dataframes
    new_row = pd.DataFrame([data_names + label_names], columns=df.columns)
    df = pd.concat([new_row, df]).reset_index(drop=True)

    # Add label names to the track columns
    for col_num, track_name in [t.split(" ") for t in label_names]:
        col_num = int(col_num) - 1
        for num, label in label_tracks[track_name].items():
            df.loc[df.iloc[:, col_num] == num, df.columns[col_num]] = f"{num} {label}"

    # Save the new file
    df.to_csv(sensors_data_file + ".new.csv", index=False, header=False, na_rep="NaN")


if __name__ == "__main__":
    main()
