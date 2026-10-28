
import joblib
from pathlib import Path
from micromlgen import port

# Newly trained model and output header
MODEL_FILE = Path("gesture_model.pkl")
OUTPUT_FILE = Path("include/gesture_model.h")

EXPECTED_CLASSES = {
    "STOP",
    "IM_OKAY",
    "WATER",
    "FOOD",
    "THANK_YOU",
    "HAVE_A_GOOD_DAY",
    "GOOD_FOR_YOU",
    "IDLE",
}


def main():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"{MODEL_FILE} not found. Run train.py first."
        )

    model = joblib.load(MODEL_FILE)

    actual_classes = set(model.classes_)

    print("Model classes:", list(model.classes_))
    print("Number of classes:", len(model.classes_))
    print("Number of features:", model.n_features_in_)

    if actual_classes != EXPECTED_CLASSES:
        raise ValueError(
            f"Expected classes: {sorted(EXPECTED_CLASSES)}\n"
            f"Actual classes: {sorted(actual_classes)}"
        )

    if model.n_features_in_ != 5:
        raise ValueError("Expected exactly 5 flex sensor features.")

    model_code = port(model, classname="GestureModel")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(model_code, encoding="utf-8")

    print(f"\nExported model to: {OUTPUT_FILE.resolve()}")
    print("Export successful.")


if __name__ == "__main__":
    main()
