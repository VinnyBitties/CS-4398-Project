"""Split labeled JSON reports before training (default 60/20/20 per class)."""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from model_utils import labels_from_records, load_records, reports_to_matrix


def split_records(records, validation_fraction=0.2, test_fraction=0.2, seed=42):
    if (not math.isfinite(validation_fraction) or not math.isfinite(test_fraction)
            or validation_fraction <= 0 or test_fraction <= 0
            or validation_fraction + test_fraction >= 1):
        raise ValueError("Validation/test fractions must be positive and sum to less than 1.")
    labels = labels_from_records(records)
    reports_to_matrix(records)  # Validate before writing any partition.
    seen_reports, seen_ids = set(), set()
    for record in records:
        report = record.get("report", record)
        fingerprint = json.dumps(report, sort_keys=True)
        job_id = report.get("job_id")
        if fingerprint in seen_reports or (job_id is not None and job_id in seen_ids):
            raise ValueError("Duplicate report or job_id: deduplicate before splitting.")
        seen_reports.add(fingerprint)
        if job_id is not None:
            seen_ids.add(job_id)
    rng = random.Random(seed)
    partitions = {"train": [], "validation": [], "test": []}
    for label in (0, 1):
        group = [record for record, value in zip(records, labels) if value == label]
        rng.shuffle(group)
        n_validation = max(1, round(len(group) * validation_fraction))
        n_test = max(1, round(len(group) * test_fraction))
        if len(group) - n_validation - n_test < 1:
            raise ValueError("Each class needs enough reports for all three partitions (at least 3).")
        partitions["validation"].extend(group[:n_validation])
        partitions["test"].extend(group[n_validation:n_validation + n_test])
        partitions["train"].extend(group[n_validation + n_test:])
    for values in partitions.values():
        rng.shuffle(values)
    partitions["train_benign"] = [r for r in partitions["train"] if r["label"] == 0]
    return partitions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("data/splits"))
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        parts = split_records(load_records(args.data), args.validation_fraction, args.test_fraction, args.seed)
        paths = [args.out_dir / (name + ".json") for name in (*parts, "split_info")]
        if any(path.exists() for path in paths):
            raise ValueError("Split outputs already exist; choose a new --out-dir.")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for name, records in parts.items():
            (args.out_dir / f"{name}.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        info = {"seed": args.seed, "validation_fraction": args.validation_fraction,
                "test_fraction": args.test_fraction,
                "counts": {name: {"total": len(rows), "malicious": sum(r["label"] for r in rows)}
                           for name, rows in parts.items()}}
        paths[-1].write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(info, indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
