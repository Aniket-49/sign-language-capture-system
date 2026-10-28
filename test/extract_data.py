import re
import csv

input_file = "device-monitor-261006-090521.log"
output_file = "training_data.csv"

labels = {"INDEX", "MIDDLE", "RING", "PINKY"}

with open(input_file, "r", errors="ignore") as f:
    lines = f.readlines()

rows = []

for line in lines:
    line = line.strip()

    parts = line.split(",")

    if len(parts) != 11:
        continue

    label = parts[0].strip().upper()

    if label not in labels:
        continue

    try:
        values = [float(x.strip()) for x in parts[1:]]
    except ValueError:
        continue

    if len(values) == 10:
        rows.append([label] + values)

with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)

    writer.writerow([
        "label",
        "flex_index",
        "flex_middle",
        "flex_ring",
        "flex_pinky",
        "accel_x",
        "accel_y",
        "accel_z",
        "gyro_x",
        "gyro_y",
        "gyro_z"
    ])

    writer.writerows(rows)

print(f"Created {output_file}")
print(f"Samples: {len(rows)}")