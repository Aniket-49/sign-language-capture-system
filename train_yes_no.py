import serial
import csv
import time
import re
import os
from collections import deque
import numpy as np

# ---------------- CONFIGURATION ----------------
PORT = "COM9"
BAUD_RATE = 115200
WINDOW_SIZE = 8
OUTPUT_FILE = "yes_no_training_data.csv"

LABELS = ["YES", "NO", "REST", "HELLO"]

# ---------------- FEATURE EXTRACTION ----------------
def extract_features(window):
    """
    Each row contains:
    thumb, ax, ay, az, gx, gy, gz

    For each signal, calculate:
    mean, standard deviation, minimum, maximum, delta.
    Total = 7 signals * 5 features = 35.
    """
    data = np.array(window, dtype=float)
    features = []

    for col in range(7):
        values = data[:, col]
        features.extend([
            np.mean(values),
            np.std(values),
            np.min(values),
            np.max(values),
            values[-1] - values[0]
        ])

    return features


def parse_line(line):
    """
    Expected serial format:
    Flex T=300 | Accel X=0.1 Y=0.2 Z=9.8 |
    Gyro X=0.0 Y=0.0 Z=0.0
    """
    patterns = [
        r"Flex\s*T\s*=\s*(-?\d+(?:\.\d+)?)",
        r"Accel\s*X\s*=\s*(-?\d+(?:\.\d+)?)",
        r"Y\s*=\s*(-?\d+(?:\.\d+)?)",
        r"Z\s*=\s*(-?\d+(?:\.\d+)?)",
        r"Gyro\s*X\s*=\s*(-?\d+(?:\.\d+)?)",
        r"Y\s*=\s*(-?\d+(?:\.\d+)?)",
        r"Z\s*=\s*(-?\d+(?:\.\d+)?)"
    ]

    values = []

    try:
        # Extract the seven numbers in the expected order.
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                return None
            values.append(float(match.group(1)))

        return values
    except (ValueError, AttributeError):
        return None


def main():
    print("\n=== SIGN LANGUAGE DATA COLLECTOR ===")
    print("Labels:", ", ".join(LABELS))
    print("Output:", OUTPUT_FILE)

    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        ser.reset_input_buffer()
    except serial.SerialException as error:
        print(f"Could not open {PORT}: {error}")
        print("Close PlatformIO Serial Monitor before running this script.")
        return

    file_exists = os.path.exists(OUTPUT_FILE)
    file_empty = not file_exists or os.path.getsize(OUTPUT_FILE) == 0

    try:
        with open(OUTPUT_FILE, "a", newline="") as file:
            writer = csv.writer(file)

            if file_empty:
                columns = []
                for name in ["thumb", "ax", "ay", "az", "gx", "gy", "gz"]:
                    columns.extend([
                        f"{name}_mean",
                        f"{name}_std",
                        f"{name}_min",
                        f"{name}_max",
                        f"{name}_delta"
                    ])
                writer.writerow(columns + ["label"])

            print("\nKeep the ESP32 powered and connected.")
            print("Enter a label to start collecting that gesture.")
            print("Enter Q to quit.\n")

            while True:
                label = input(
                    f"Label {LABELS} or Q: "
                ).strip().upper()

                if label == "Q":
                    break

                if label not in LABELS:
                    print("Invalid label. Try again.")
                    continue

                input(
                    f"\nPrepare the {label} gesture. "
                    "Press ENTER, then perform it repeatedly. "
                    "Press ENTER again to stop.\n"
                )

                print(f"Collecting {label}... Press ENTER to stop.")
                window = deque(maxlen=WINDOW_SIZE)
                count = 0
                stop_collection = False

                # Use a separate thread to allow ENTER to stop collection.
                import threading
                stop_event = threading.Event()

                def wait_for_enter():
                    input()
                    stop_event.set()

                threading.Thread(
                    target=wait_for_enter, daemon=True
                ).start()

                while not stop_event.is_set():
                    raw = ser.readline().decode(
                        "utf-8", errors="ignore"
                    ).strip()

                    values = parse_line(raw)
                    if values is None:
                        continue

                    window.append(values)

                    if len(window) == WINDOW_SIZE:
                        features = extract_features(window)
                        writer.writerow(features + [label])
                        count += 1

                        if count % 25 == 0:
                            file.flush()
                            print(
                                f"\r{label}: {count} windows saved",
                                end="",
                                flush=True
                            )

                file.flush()
                print(f"\nSaved {count} windows for {label}.\n")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ser.close()

    print("Data collection finished.")


if __name__ == "__main__":
    main()