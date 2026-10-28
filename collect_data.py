
import csv
import time
import serial
from pathlib import Path

PORT = "COM9"
BAUD = 115200
SAMPLES_PER_GESTURE = 100
OUTPUT_FILE = Path("training_data_static.csv")

GESTURES = [
    "STOP",
    "IM_OKAY",
    "WATER",
    "FOOD",
    "THANK_YOU",
    "HAVE_A_GOOD_DAY",
    "GOOD_FOR_YOU",
    "IDLE",
]

COLUMNS = ["thumb", "index", "middle", "ring", "pinky", "label"]


def parse_reading(line):
    try:
        values = [int(v.strip()) for v in line.split(",")]
        if len(values) != 5:
            return None
        if any(v < 0 or v > 4095 for v in values):
            return None
        if all(v == 0 for v in values):
            return None
        return values
    except ValueError:
        return None


def main():
    print("NEW STATIC SIGN DATA COLLECTOR")
    print("Classes:", ", ".join(GESTURES))
    print("Output:", OUTPUT_FILE.resolve())

    if input("Type COLLECT to start: ").strip() != "COLLECT":
        print("Cancelled.")
        return

    try:
        ser = serial.Serial(PORT, BAUD, timeout=2)
    except serial.SerialException as e:
        print("Could not open serial port:", e)
        print("Close PlatformIO Monitor and check COM9.")
        return

    try:
        time.sleep(2)
        ser.reset_input_buffer()

        with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)

            for gesture in GESTURES:
                input(
                    f"\nPrepare {gesture}. Hold the pose, "
                    "then press Enter to collect 100 samples."
                )

                ser.reset_input_buffer()
                time.sleep(0.5)
                collected = 0
                attempts = 0

                while collected < SAMPLES_PER_GESTURE:
                    line = ser.readline().decode(
                        "utf-8", errors="ignore"
                    ).strip()
                    attempts += 1

                    values = parse_reading(line)
                    if values is not None:
                        writer.writerow(values + [gesture])
                        collected += 1

                        if collected % 20 == 0:
                            print(
                                f"{gesture}: {collected}/"
                                f"{SAMPLES_PER_GESTURE}"
                            )

                    if attempts >= 2000 and collected == 0:
                        raise RuntimeError(
                            "No valid readings. Check ESP32 output."
                        )

                f.flush()
                print(f"Saved {gesture}: {collected} samples.")

        print("\nCollection complete: 800 samples planned.")
        print("CSV:", OUTPUT_FILE.resolve())

    except KeyboardInterrupt:
        print("\nInterrupted. The CSV may be incomplete.")
    except (OSError, RuntimeError) as e:
        print("\nCollection stopped:", e)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
