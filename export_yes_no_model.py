
import joblib
from pathlib import Path
from micromlgen import port

MODEL_FILE = Path("yes_no_model.pkl")
OUTPUT_FILE = Path("include/yes_no_model.h")

def main():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            "yes_no_model.pkl not found. Run train_yes_no.py first."
        )

    model = joblib.load(MODEL_FILE)

    print("Model classes:", list(model.classes_))
    print("Number of classes:", len(model.classes_))
    print("Number of features:", model.n_features_in_)

    if len(model.classes_) != 3:
        raise ValueError("Expected YES, NO, and REST classes.")

    if model.n_features_in_ != 35:
        raise ValueError("Expected exactly 35 MPU/flex features.")

    model_code = port(model, classname="YesNoModel")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(model_code, encoding="utf-8")

    print(f"\nExported model to: {OUTPUT_FILE.resolve()}")
    print("Export successful.")

if __name__ == "__main__":
    main()
