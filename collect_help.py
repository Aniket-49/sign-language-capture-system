
import csv
import re
import time
import serial
from pathlib import Path

PORT = "COM9"
BAUD = 115200
SAMPLES = 100
OUTPUT_FILE = Path("help_samples.csv")

COLUMNS = ["thumb", "index", "middle", "ring", "pinky", "label"]

def parse_reading(line):
    # Matches the current ESP32 Serial Monitor format.
    pattern = (
        r"Thumb:\s*(\d+)\s*\|\s*"
        r"Index:\s*(\d+)\s*\|\s*"
        r"Middle:\s*(\d+)\s*\|\s*"
        r"Ring:\s*(\d+)\s*\|\s*"
        r"Pinky:\s*(\d+)"
    )

    match = re.search(pattern, line, re.IGNORECASE)
    if not match:
        return None

    values = [int(x) for x in match.groups()]

    if any(v < 0 or v > 4095 for v in values):
        return None

    if all(v == 0 for v in values):
        return None

    return values

def main():
    print("HELP GESTURE DATA COLLECTION")
    print(f"Output: {OUTPUT_FILE.resolve()}")
    print(f"Samples to collect: {SAMPLES}")

    if OUTPUT_FILE.exists():
        print("ERROR: help_samples.csv already exists.")
        print("Rename or back it up before collecting again.")
        return

    try:
        ser = serial.Serial(PORT, BAUD, timeout=2)
    except serial.SerialException as e:
        print(f"Cannot open {PORT}: {e}")
        print("Close PlatformIO Monitor and try again.")
        return

    collected = 0

    try:
        time.sleep(2)
        ser.reset_input_buffer()

        input(
            "\nWear the glove and make the HELP pose:\n"
            "Four fingers extended, thumb tucked across the palm.\n"
            "Hold it steadily, then press Enter to collect."
        )

        with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)

            while collected < SAMPLES:
                line = ser.readline().decode(
                    "utf-8", errors="ignore"
                ).strip()

                values = parse_reading(line)
                if values is None:
                    continue

                writer.writerow(values + ["HELP"])
                collected += 1

                if collected % 10 == 0:
                    f.flush()
                    print(f"HELP: {collected}/{SAMPLES}")

        print(f"\nFinished. Saved {collected} HELP samples.")
        print(f"File: {OUTPUT_FILE.resolve()}")
        print("Your existing training dataset was not modified.")

    except KeyboardInterrupt:
        print(f"\nStopped. Collected {collected} samples.")
        print("The HELP file may be incomplete.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
