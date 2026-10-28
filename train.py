
import pandas as pd
import joblib

from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# Files
DATA_FILE = Path("training_data.csv")
MODEL_FILE = Path("gesture_model.pkl")

# Five flex sensor features
FEATURES = ["thumb", "index", "middle", "ring", "pinky"]

# Eight classes collected in collect_8_signs.py
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
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"{DATA_FILE} not found. "
            "Run collect_8_signs.py first."
        )

    df = pd.read_csv(DATA_FILE)

    required = FEATURES + ["label"]
    missing = set(required) - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing CSV columns: {sorted(missing)}\n"
            f"Actual columns: {list(df.columns)}"
        )

    # Clean data
    df = df.dropna(subset=required).copy()
    df["label"] = df["label"].astype(str).str.strip()

    df[FEATURES] = df[FEATURES].apply(
        pd.to_numeric, errors="coerce"
    )
    df = df.dropna(subset=FEATURES)

    # Validate sensor readings
    valid = (
        df[FEATURES].ge(0).all(axis=1)
        & df[FEATURES].le(4095).all(axis=1)
        & df[FEATURES].ne(0).any(axis=1)
    )
    df = df[valid].copy()

    actual_classes = set(df["label"].unique())
    missing_classes = EXPECTED_CLASSES - actual_classes
    unexpected_classes = actual_classes - EXPECTED_CLASSES

    if missing_classes or unexpected_classes:
        raise ValueError(
            f"Missing classes: {sorted(missing_classes)}\n"
            f"Unexpected classes: {sorted(unexpected_classes)}\n"
            "Check the labels in training_data.csv."
        )

    print("\nSamples per class:")
    print(df["label"].value_counts().sort_index())
    print(f"\nTotal valid samples: {len(df)}")

    counts = df["label"].value_counts()
    if (counts < 2).any():
        raise ValueError(
            "Each class needs at least two valid samples."
        )

    X = df[FEATURES]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced",
    )

    print("\nTraining Random Forest...")
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)

    print(f"\nTest accuracy: {accuracy:.2%}")
    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=sorted(EXPECTED_CLASSES),
            zero_division=0,
        )
    )

    joblib.dump(model, MODEL_FILE)

    print(f"\nModel saved to: {MODEL_FILE.resolve()}")
    print("Classes:", list(model.classes_))
    print("\nTraining complete.")


if __name__ == "__main__":
    main()
