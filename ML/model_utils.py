from __future__ import annotations

# Loads labeled records and converts reports into matrices and labels for model training.

import json
from pathlib import Path
from typing import Any

import numpy as np

from config import FEATURE_COLUMNS
from report_parser import extract_features


def load_records(source: str | Path) -> list[dict[str, Any]]:
    path = Path(source)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Training data must be a JSON array of records.")
    return data


def reports_to_matrix(records: list[Any]) -> np.ndarray:
    if not records:
        raise ValueError("Dataset must contain at least one report.")
    reports = [record.get("report", record) if isinstance(record, dict) else record for record in records]
    features = [extract_features(report) for report in reports]
    return np.array(
        [[row[column] for column in FEATURE_COLUMNS] for row in features],
        dtype=float,
    )


def labels_from_records(records: list[dict[str, Any]]) -> np.ndarray:
    if not records:
        raise ValueError("Dataset must contain at least one labeled report.")
    for index, record in enumerate(records):
        if (not isinstance(record, dict) or type(record.get("label")) is not int
                or record["label"] not in (0, 1)):
            raise ValueError(f"Record {index}: label must be an integer 0 or 1.")
    return np.array([record["label"] for record in records], dtype=int)


def benign_training_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if np.any(labels_from_records(records) != 0):
        raise ValueError("Isolation Forest training requires only records labeled 0 (benign).")
    return records
