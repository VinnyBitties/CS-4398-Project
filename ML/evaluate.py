from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
	accuracy_score,
	classification_report,
	confusion_matrix,
	f1_score,
	precision_score,
	recall_score,
	roc_auc_score,
)

from model_utils import labels_from_records, load_records, reports_to_matrix


def build_argument_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Evaluate a trained malware detection model.")
	parser.add_argument("--data", required=True, help="JSON array of test records.")
	parser.add_argument("--model", required=True, help="Saved .joblib model to evaluate.")
	parser.add_argument(
		"--model-type",
		required=True,
		choices=("classifier", "anomaly"),
		help="Type of the saved model.",
	)
	return parser


def classification_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
	return {
		"accuracy": accuracy_score(actual, predicted),
		"precision": precision_score(actual, predicted, zero_division=0),
		"recall": recall_score(actual, predicted, zero_division=0),
		"f1_score": f1_score(actual, predicted, zero_division=0),
		"confusion_matrix": confusion_matrix(actual, predicted).tolist(),
		"classification_report": classification_report(
			actual,
			predicted,
			zero_division=0,
			output_dict=True,
		),
	}


def evaluate_classifier(model: Any, features: np.ndarray, records: list[dict[str, Any]]) -> dict[str, Any]:
	actual = labels_from_records(records)
	if not hasattr(model, "predict"):
		raise ValueError("The classifier model does not support predict().")

	predicted = np.asarray(model.predict(features))
	results = classification_metrics(actual, predicted)

	if hasattr(model, "predict_proba"):
		probabilities = np.asarray(model.predict_proba(features))
		classes = np.asarray(getattr(model, "classes_", []))
		if probabilities.ndim == 2 and probabilities.shape[1] > 1 and 1 in classes:
			try:
				malicious_index = int(np.where(classes == 1)[0][0])
				results["roc_auc"] = roc_auc_score(
					actual,
					probabilities[:, malicious_index],
				)
			except ValueError:
				pass

	return results


def evaluate_anomaly(model: Any, features: np.ndarray, records: list[dict[str, Any]]) -> dict[str, Any]:
	if not hasattr(model, "predict"):
		raise ValueError("The anomaly model does not support predict().")

	predictions = np.asarray(model.predict(features))
	anomaly_count = int(np.count_nonzero(predictions == -1))
	known_count = int(np.count_nonzero(predictions == 1))
	total = len(predictions)
	results: dict[str, Any] = {
		"anomaly_count": anomaly_count,
		"anomaly_percentage": anomaly_count / total * 100,
		"known_count": known_count,
		"known_percentage": known_count / total * 100,
	}

	if all(isinstance(record, dict) and "label" in record for record in records):
		actual = labels_from_records(records)
		predicted_labels = (predictions == -1).astype(int)
		results["classification"] = classification_metrics(actual, predicted_labels)

	return results


def to_jsonable(value: Any) -> Any:
	if isinstance(value, np.ndarray):
		return value.tolist()
	if isinstance(value, np.generic):
		return value.item()
	if isinstance(value, dict):
		return {str(key): to_jsonable(item) for key, item in value.items()}
	if isinstance(value, list):
		return [to_jsonable(item) for item in value]
	return value


def main() -> None:
	parser = build_argument_parser()
	args = parser.parse_args()

	try:
		records = load_records(args.data)
		if not records:
			raise ValueError("Test dataset must contain at least one record.")

		features = reports_to_matrix(records)
		model = joblib.load(Path(args.model))
		if args.model_type == "classifier":
			results = evaluate_classifier(model, features, records)
		else:
			results = evaluate_anomaly(model, features, records)
	except (OSError, ValueError) as exc:
		parser.error(str(exc))

	print(json.dumps(to_jsonable(results), indent=2))


if __name__ == "__main__":
	main()
