
import csv
import re
import time
import serial
from pathlib import Path

PORT = "COM9"
BAUD = 115200
SAMPLES = 100

SIGNS = [
    "THANK_YOU",
    "IM_OKAY",
    "FOOD",
    "HAVE_A_GOOD_DAY",
    "GOOD_FOR_YOU",
    "WATER",
    "IDLE",
    "STOP",
]

OUTPUT = Path(__file__).parent / "training_data.csv"

PATTERN = re.compile(
    r"Thumb:\s*(-?\d+)\s*\|\s*"
    r"Index:\s*(-?\d+)\s*\|\s*"
    r"Middle:\s*(-?\d+)\s*\|\s*"
    r"Ring:\s*(-?\d+)\s*\|\s*"
    r"Pinky:\s*(-?\d+)"
)

def main():
    print("8-SIGN TRAINING DATA COLLECTION")
    print("Close PlatformIO Monitor before continuing.")
    input("Press ENTER to connect...")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except Exception as e:
        print("Serial connection failed:", e)
        return

    time.sleep(2)
    ser.reset_input_buffer()

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "thumb", "index", "middle", "ring", "pinky", "label"
        ])

        total = 0

        for sign in SIGNS:
            input(f"\nMake {sign}, hold steady, then press ENTER...")

            count = 0
            last_data = time.time()

            while count < SAMPLES:
                line = ser.readline().decode(
                    "utf-8", errors="ignore"
                ).strip()

                match = PATTERN.search(line)

                if match:
                    values = [int(x) for x in match.groups()]

                    if all(x == 0 for x in values):
                        continue

                    writer.writerow(values + [sign])
                    f.flush()
                    count += 1
                    total += 1
                    last_data = time.time()

                    if count % 10 == 0:
                        print(f"{sign}: {count}/{SAMPLES}")

                elif time.time() - last_data > 10:
                    print("No matching sensor readings received.")
                    print("Last serial line:", line)
                    ser.close()
                    return

            print(f"{sign} complete: 100 samples")

    ser.close()
    print(f"\nDone! Saved {total} samples to {OUTPUT}")

if __name__ == "__main__":
    main()
