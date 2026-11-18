"""Choose a classifier threshold on validation data by maximizing malicious-class F1."""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import f1_score

from evaluate import malicious_probabilities
from model_utils import labels_from_records, load_records, reports_to_matrix


def select_threshold(labels, probabilities):
    labels = np.asarray(labels)
    probabilities = np.asarray(probabilities, dtype=float)
    if (labels.ndim != 1 or probabilities.shape != labels.shape
            or set(labels) != {0, 1}):
        raise ValueError("Validation requires both classes and one probability per record.")
    if not np.all(np.isfinite(probabilities)) or np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("Probabilities must be finite and between 0 and 1.")
    candidates = np.unique(np.concatenate(([0.0, 0.5, 1.0], probabilities)))
    # Deterministic ties: closest to 0.5, then higher threshold.
    scores = [(float(f1_score(labels, probabilities >= t, zero_division=0)), float(t))
              for t in candidates]
    score, threshold = max(scores, key=lambda pair: (pair[0], -abs(pair[1] - 0.5), pair[1]))
    return {"threshold": threshold, "validation_f1": score,
            "selection_metric": "malicious_class_f1", "validation_count": len(labels)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-data", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", type=Path, default=Path("models/threshold.json"))
    args = parser.parse_args()
    try:
        records = load_records(args.validation_data)
        labels = labels_from_records(records)
        model = joblib.load(args.model)
        result = select_threshold(labels, malicious_probabilities(model, reports_to_matrix(records)))
        result["model_path"] = str(Path(args.model).resolve())
        result["validation_data"] = str(Path(args.validation_data).resolve())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
