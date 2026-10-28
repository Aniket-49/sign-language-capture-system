
from pathlib import Path
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "training_data.csv"
MODEL_PATH = ROOT / "gesture_model.pkl"

FEATURES = ["thumb", "index", "middle", "ring", "pinky"]
LABEL = "label"
EXPECTED_CLASSES = {"A", "B", "C", "D", "E", "IDLE"}

if not CSV_PATH.exists():
    raise FileNotFoundError(f"Dataset not found: {CSV_PATH}")

df = pd.read_csv(CSV_PATH)
df.columns = df.columns.str.strip()

required = FEATURES + [LABEL]
missing = [col for col in required if col not in df.columns]

if missing:
    raise ValueError(f"Missing CSV columns: {missing}")

df = df[required].copy()
df[FEATURES] = df[FEATURES].apply(pd.to_numeric, errors="coerce")
df[LABEL] = df[LABEL].astype(str).str.strip()
df = df.dropna(subset=required)

print("\nSamples per class:")
print(df[LABEL].value_counts())

found = set(df[LABEL].unique())
missing_classes = EXPECTED_CLASSES - found

if missing_classes:
    raise ValueError(
        f"Missing classes: {sorted(missing_classes)}. "
        "Do not train until all six classes are collected."
    )

counts = df[LABEL].value_counts()

if (counts < 2).any():
    raise ValueError("Every class needs at least two samples.")

X = df[FEATURES]
y = df[LABEL]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.25,
    random_state=42,
    stratify=y
)

model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)
predictions = model.predict(X_test)

print(
    "\nTest accuracy:",
    round(accuracy_score(y_test, predictions) * 100, 2),
    "%"
)

print("\nClassification report:")
print(classification_report(y_test, predictions, zero_division=0))

joblib.dump(model, MODEL_PATH)

print(f"\nModel saved to: {MODEL_PATH}")
print("Features:", FEATURES)
print("Classes:", list(model.classes_))
