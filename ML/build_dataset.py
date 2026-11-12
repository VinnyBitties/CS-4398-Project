"""
Turns a manifest of (report_path, label) pairs into training JSON records
or a flat feature CSV. Both exports validate reports with extract_features(),
the same function used during training and inference.

Input manifest format (CSV, header required):
    report_path,label
    data/synthetic_reports/report_00000.json,0
    data/synthetic_reports/report_00001.json,1

Output features CSV columns:
    FEATURE_COLUMNS... , label

Usage:
    python build_dataset.py
    python build_dataset.py --manifest data/manifest.csv --out data/features.csv
    python build_dataset.py --manifest data/manifest.csv --out data/records.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from config import FEATURE_COLUMNS, FEATURES_CSV_PATH, MANIFEST_PATH
from report_parser import extract_features, load_report


def read_manifest(manifest_path: Path) -> list[tuple[Path, int]]:
    rows: list[tuple[Path, int]] = []
    with manifest_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or {"report_path", "label"} - set(reader.fieldnames):
            raise ValueError(
                f"Manifest {manifest_path} must have 'report_path,label' columns, "
                f"found: {reader.fieldnames}"
            )
        for line, row in enumerate(reader, start=2):
            if not row.get("report_path") or row.get("label") not in {"0", "1"}:
                raise ValueError(f"Manifest row {line} requires a report_path and label 0 or 1")
            # Preserve existing semantics: relative paths are relative to cwd.
            rows.append((Path(row["report_path"]), int(row["label"])))
    return rows


def build_records(manifest: list[tuple[Path, int]]) -> list[dict[str, Any]]:
    """Keep original reports and external labels; reject invalid input before export."""
    if not manifest:
        raise ValueError("Manifest must contain at least one report")
    records: list[dict[str, Any]] = []
    for report_path, label in manifest:
        if type(label) is not int or label not in (0, 1):
            raise ValueError(f"{report_path}: label must be 0 or 1")
        try:
            report = load_report(report_path)
            extract_features(report)
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid report {report_path}: {exc}") from exc
        records.append({"report": report, "label": label})
    return records


def build_feature_rows(manifest: list[tuple[Path, int]]) -> list[dict[str, int]]:
    return [{**extract_features(record["report"]), "label": record["label"]}
            for record in build_records(manifest)]


def write_records_json(records: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def write_features_csv(feature_rows: list[dict[str, int]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [*FEATURE_COLUMNS, "label"]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in feature_rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build training JSON records or a feature CSV from a report manifest.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, help="Output path; .json selects JSON unless --format is specified.")
    parser.add_argument("--format", choices=("csv", "json"), help="Export format (default: inferred from --out, otherwise CSV).")
    args = parser.parse_args()

    output_format = args.format or ("json" if args.out and args.out.suffix.lower() == ".json" else "csv")
    out_path = args.out or (FEATURES_CSV_PATH.with_name("records.json")
                            if output_format == "json" else FEATURES_CSV_PATH)
    try:
        manifest = read_manifest(args.manifest)
        # Complete validation before opening the output, including CSV exports.
        records = build_records(manifest)
        if output_format == "json":
            write_records_json(records, out_path)
        else:
            rows = [{**extract_features(r["report"]), "label": r["label"]} for r in records]
            write_features_csv(rows, out_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    n_malicious = sum(r["label"] for r in records)
    print(f"Wrote {len(records)} {output_format.upper()} records -> {out_path}")
    print(f"  malicious: {n_malicious}  benign: {len(records) - n_malicious}")


if __name__ == "__main__":
    main()
