"""
Turns a manifest of (report_path, label) pairs into a flat feature-matrix CSV
using the same extract_features() that predict.py uses at inference time --
this is what keeps training and inference features from ever drifting apart.

Input manifest format (CSV, header required):
    report_path,label
    data/synthetic_reports/report_00000.json,0
    data/synthetic_reports/report_00001.json,1

Output features CSV columns:
    FEATURE_COLUMNS... , label

Usage:
    python build_dataset.py
    python build_dataset.py --manifest data/manifest.csv --out data/features.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

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
        for row in reader:
            rows.append((Path(row["report_path"]), int(row["label"])))
    return rows


def build_feature_rows(manifest: list[tuple[Path, int]]) -> list[dict[str, int]]:
    feature_rows: list[dict[str, int]] = []
    skipped = 0

    for report_path, label in manifest:
        try:
            report = load_report(report_path)
        except Exception as exc:  # noqa: BLE001 - keep building the dataset past bad files
            print(f"  skipping {report_path}: failed to load ({exc})")
            skipped += 1
            continue

        features = extract_features(report)
        row = {**features, "label": label}
        feature_rows.append(row)

    if skipped:
        print(f"Skipped {skipped} report(s) that failed to load.")

    return feature_rows


def write_features_csv(feature_rows: list[dict[str, int]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [*FEATURE_COLUMNS, "label"]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in feature_rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a feature-matrix CSV from a report manifest.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, default=FEATURES_CSV_PATH)
    args = parser.parse_args()

    manifest = read_manifest(args.manifest)
    print(f"Loaded manifest with {len(manifest)} entries from {args.manifest}")

    feature_rows = build_feature_rows(manifest)
    write_features_csv(feature_rows, args.out)

    n_malicious = sum(r["label"] for r in feature_rows)
    print(f"Wrote {len(feature_rows)} feature rows -> {args.out}")
    print(f"  malicious: {n_malicious}  benign: {len(feature_rows) - n_malicious}")


if __name__ == "__main__":
    main()