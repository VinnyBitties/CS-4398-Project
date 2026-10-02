from __future__ import annotations

import argparse
from pathlib import Path

import joblib
from sklearn.ensemble import IsolationForest

from model_utils import load_records, reports_to_matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Train an Isolation Forest novelty detector.")
    parser.add_argument("--data", required=True, help="JSON array of known benign reports.")
    parser.add_argument("--model-out", default="isolation_forest.joblib")
    parser.add_argument("--contamination", default="auto", type=lambda value: value if value == "auto" else float(value))
    args = parser.parse_args()

    records = load_records(args.data)
    features = reports_to_matrix(records)
    model = IsolationForest(
        contamination=args.contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(features)
    joblib.dump(model, Path(args.model_out))
    print(f"Saved Isolation Forest model to {args.model_out}")


if __name__ == "__main__":
    main()