from __future__ import annotations

import argparse
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier

from model_utils import labels_from_records, load_records, reports_to_matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a Random Forest malware classifier.")
    parser.add_argument("--data", required=True, help="JSON array of records with report and label fields.")
    parser.add_argument("--model-out", default="random_forest.joblib")
    parser.add_argument("--trees", type=int, default=200)
    args = parser.parse_args()

    records = load_records(args.data)
    features = reports_to_matrix(records)
    labels = labels_from_records(records)
    if len(set(labels)) < 2:
        raise ValueError("Random Forest training requires both benign and malicious labels.")

    model = RandomForestClassifier(
        n_estimators=args.trees,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(features, labels)
    joblib.dump(model, Path(args.model_out))
    print(f"Saved Random Forest model to {args.model_out}")


if __name__ == "__main__":
    main()