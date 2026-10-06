from __future__ import annotations

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
    reports = [record.get("report", record) if isinstance(record, dict) else record for record in records]
    return np.array(
        [[extract_features(report).get(column, 0) for column in FEATURE_COLUMNS] for report in reports],
        dtype=float,
    )


def labels_from_records(records: list[dict[str, Any]]) -> np.ndarray:
    try:
        return np.array([int(record["label"]) for record in records], dtype=int)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Each classifier record must contain a numeric "label".') from exc