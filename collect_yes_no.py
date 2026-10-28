
import csv
import re
import time
from pathlib import Path
from collections import deque

import numpy as np
import serial
from serial.tools import list_ports

# ---------------- CONFIGURATION ----------------
SERIAL_PORT = "COM9"
BAUD_RATE = 115200
OUTPUT_FILE = Path("yes_no_training_data.csv")

WINDOW_SIZE = 8
SAMPLE_INTERVAL_SECONDS = 0.2

FEATURES = [
    "thumb_mean", "thumb_std", "thumb_min", "thumb_max", "thumb_delta",
    "ax_mean", "ax_std", "ax_min", "ax_max", "ax_delta",
    "ay_mean", "ay_std", "ay_min", "ay_max", "ay_delta",
    "az_mean", "az_std", "az_min", "az_max", "az_delta",
    "gx_mean", "gx_std", "gx_min", "gx_max", "gx_delta",
    "gy_mean", "gy_std", "gy_min", "gy_max", "gy_delta",
    "gz_mean", "gz_std", "gz_min", "gz_max", "gz_delta",
]

LABELS = ("YES", "NO", "REST")

# Matches the diagnostic lines printed by the current main.cpp.
LINE_PATTERN = re.compile(
    r"Flex T=(?P<thumb>-?\d+(?:\.\d+)?)"
    r".*?Accel X=(?P<ax>-?\d+(?:\.\d+)?)"
    r"\s+Y=(?P<ay>-?\d+(?:\.\d+)?)"
    r"\s+Z=(?P<az>-?\d+(?:\.\d+)?)"
    r".*?Gyro X=(?P<gx>-?\d+(?:\.\d+)?)"
    r"\s+Y=(?P<gy>-?\d+(?:\.\d+)?)"
    r"\s+Z=(?P<gz>-?\d+(?:\.\d+)?)"
)


def extract_reading(line):
    match = LINE_PATTERN.search(line)
    if not match:
        return None

    return [
        float(match.group("thumb")),
        float(match.group("ax")),
        float(match.group("ay")),
        float(match.group("az")),
        float(match.group("gx")),
        float(match.group("gy")),
        float(match.group("gz")),
    ]


def calculate_features(window):
    values = np.asarray(window, dtype=float)
    result = []

    for signal_index in range(7):
        signal = values[:, signal_index]

        result.extend([
            float(np.mean(signal)),
            float(np.std(signal, ddof=0)),
            float(np.min(signal)),
            float(np.max(signal)),
            float(signal[-1] - signal[0]),
        ])

    return result


def collect_class(ser, label, duration, writer):
    print(f"\nPrepare the glove for: {label}")
    input("Press ENTER when ready to start collecting...")

    ser.reset_input_buffer()
    window = deque(maxlen=WINDOW_SIZE)
    captured = 0
    invalid_lines = 0
    start = time.monotonic()

    print(f"Collecting {label} for {duration} seconds...")
    print("Keep performing the selected sign during collection.")

    while time.monotonic() - start < duration:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
        except serial.SerialException as error:
            print(f"Serial error: {error}")
            return 0

        reading = extract_reading(line)

        if reading is None:
            if line:
                invalid_lines += 1
            continue

        window.append(reading)

        if len(window) == WINDOW_SIZE:
            features = calculate_features(window)
            writer.writerow(features + [label])
            captured += 1

    print(f"Saved {captured} windows for {label}.")

    if captured == 0:
        print("No usable sensor lines were detected.")
        print("Check the COM port and the ESP32 Serial Monitor output.")

    return captured


def main():
    print("Available serial ports:")
    for port in list_ports.comports():
        print(f"  {port.device}: {port.description}")

    if not OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(FEATURES + ["label"])

    print(f"\nOutput file: {OUTPUT_FILE.resolve()}")
    print("Close the Arduino/PlatformIO Serial Monitor before continuing.")

    try:
        ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=1
        )
    except serial.SerialException as error:
        print(f"\nCould not open {SERIAL_PORT}: {error}")
        print("Change SERIAL_PORT to the ESP32's actual COM port.")
        return

    time.sleep(2)

    try:
        with OUTPUT_FILE.open(
            "a", newline="", encoding="utf-8"
        ) as file:
            writer = csv.writer(file)
            total = 0

            print("\nCollect each class separately.")
            print("Use distinct, representative samples for each sign.")

            for label in LABELS:
                while True:
                    value = input(
                        f"\nCollection duration for {label} in seconds "
                        "(e.g. 20): "
                    ).strip()

                    try:
                        duration = float(value)
                        if duration > 0:
                            break
                    except ValueError:
                        pass

                    print("Enter a positive number.")

                total += collect_class(
                    ser, label, duration, writer
                )
                file.flush()

    except KeyboardInterrupt:
        print("\nCollection interrupted.")
    finally:
        ser.close()

    print(f"\nFinished. Total windows collected: {total}")
    print(f"Training data saved to: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
