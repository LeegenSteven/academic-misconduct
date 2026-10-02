"""Validate the committed seed=42 audit snapshot and print counts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


REQUIRED = {
    "source_name", "citation_id", "annotator_2_label", "annotator_2_evidence_status",
    "project_label", "adjudicated_label", "split", "natural_or_constructed",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "data/processed/seed42_source_audit_ly_v19.csv")
    args = parser.parse_args()
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - fields)
        if missing:
            raise SystemExit(f"missing required columns: {missing}")
        rows = list(reader)

    if len(rows) != 60:
        raise SystemExit(f"expected 60 rows, got {len(rows)}")
    if len({row["citation_id"] for row in rows}) != len(rows):
        raise SystemExit("citation_id values are not unique")
    if any(row["project_label"].strip() or row["adjudicated_label"].strip() for row in rows):
        raise SystemExit("snapshot must not contain project or adjudicated labels")

    summary = {}
    for source in ("SciFact", "ReferenceErrorDetection"):
        subset = [row for row in rows if row["source_name"] == source]
        summary[source] = {
            "rows": len(subset),
            "annotator_2_status": Counter(row["annotator_2_evidence_status"] for row in subset),
            "annotator_2_label": Counter(row["annotator_2_label"] for row in subset),
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
