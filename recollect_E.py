
import csv
import re
import time
import serial
from pathlib import Path

PORT = "COM9"
BAUD = 115200
DATA_FILE = Path("training_data.csv")
SAMPLES_PER_TRIAL = 20
TRIALS = 5

pattern = re.compile(
    r"Thumb:\s*(-?\d+)\s*\|\s*"
    r"Index:\s*(-?\d+)\s*\|\s*"
    r"Middle:\s*(-?\d+)\s*\|\s*"
    r"Ring:\s*(-?\d+)\s*\|\s*"
    r"Pinky:\s*(-?\d+)"
)

print("E training: bend ONLY your thumb.")
print("Keep index, middle, ring and pinky straight.")
print("Close PlatformIO Serial Monitor before continuing.")

input("Press ENTER to connect to ESP32...")

new_samples = []

try:
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        time.sleep(2)
        ser.reset_input_buffer()

        for trial in range(1, TRIALS + 1):
            input(
                f"\nTrial {trial}/{TRIALS}: "
                "Set E gesture, then press ENTER..."
            )

            print("Recording for 3 seconds...")
            start = time.time()
            collected = 0

            while time.time() - start < 3:
                line = ser.readline().decode(
                    "utf-8", errors="ignore"
                ).strip()

                match = pattern.search(line)
                if not match:
                    continue

                values = [int(v) for v in match.groups()]

                new_samples.append(values + ["E"])
                collected += 1

                print(
                    f"Thumb={values[0]}  Index={values[1]}  "
                    f"Middle={values[2]}  Ring={values[3]}  "
                    f"Pinky={values[4]}  ({collected})"
                )

            print(f"Trial saved: {collected} samples")

except KeyboardInterrupt:
    print("\nCollection interrupted.")

if new_samples:
    with DATA_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(new_samples)

print(f"\nNew E samples collected: {len(new_samples)}")
print(f"Dataset: {DATA_FILE.resolve()}")
