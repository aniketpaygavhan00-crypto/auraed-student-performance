"""Train this demo model. Replace the synthetic CSV with real, consented data."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "sample_student_data.csv"
MODEL_PATH = ROOT / "model" / "student_model.joblib"
FEATURES = ["study_hours", "attendance", "previous_score"]
TARGET = "final_score"


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Training data not found: {DATA_PATH}")
    data = pd.read_csv(DATA_PATH)
    missing = set(FEATURES + [TARGET]) - set(data.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
    data = data[FEATURES + [TARGET]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(data) < 8:
        raise ValueError("Provide at least 8 complete training rows.")
    valid_ranges = {
        "study_hours": (0, 24),
        "attendance": (0, 100),
        "previous_score": (0, 100),
        "final_score": (0, 100),
    }
    for column, (lower, upper) in valid_ranges.items():
        if not data[column].between(lower, upper).all():
            raise ValueError(f"{column} values must be between {lower} and {upper}.")

    model = make_pipeline(StandardScaler(), LinearRegression())
    model.fit(data[FEATURES], data[TARGET])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Trained on {len(data)} rows and saved model to {MODEL_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
