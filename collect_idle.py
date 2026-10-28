import csv
import re
import time
import serial
from pathlib import Path

PORT = "COM9"
BAUD = 115200
TARGET_SAMPLES = 300

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "training_data.csv"

# Matches serial output such as:
# 112,145,43,149,138,E
# or:
# Thumb: 112 | Index: 145 | Middle: 43 | Ring: 149 | Pinky: 138

def parse_readings(line):
    values = line.strip().split(",")

    if len(values) >= 5:
        try:
            return [int(v.strip()) for v in values[:5]]
        except ValueError:
            pass

    match = re.search(
        r"Thumb:\s*(\d+)\s*\|\s*"
        r"Index:\s*(\d+)\s*\|\s*"
        r"Middle:\s*(\d+)\s*\|\s*"
        r"Ring:\s*(\d+)\s*\|\s*"
        r"Pinky:\s*(\d+)",
        line,
        re.IGNORECASE,
    )

    if match:
        return [int(v) for v in match.groups()]

    return None


def main():
    print("Close the PlatformIO Serial Monitor first.")
    input("Press ENTER to connect to the ESP32...")

    saved = 0

    try:
        with serial.Serial(PORT, BAUD, timeout=2) as esp:
            time.sleep(2)
            esp.reset_input_buffer()

            input(
                "\nKeep your hand relaxed, with all fingers "
                "in your normal idle position. Press ENTER to start..."
            )

            print("\nCollecting IDLE samples. Keep your hand relaxed.")

            with open(CSV_PATH, "a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)

                while saved < TARGET_SAMPLES:
                    line = esp.readline().decode(
                        "utf-8", errors="ignore"
                    ).strip()

                    readings = parse_readings(line)

                    if readings is None:
                        continue

                    writer.writerow(readings + ["IDLE"])
                    saved += 1

                    if saved % 25 == 0:
                        file.flush()
                        print(f"Saved {saved}/{TARGET_SAMPLES} IDLE samples")

            print(f"\nFinished. Added {saved} IDLE samples.")
            print(f"Dataset: {CSV_PATH}")

    except serial.SerialException as error:
        print(f"\nSerial error: {error}")
        print("Check COM9 and close other serial monitors.")


if __name__ == "__main__":
    main()
