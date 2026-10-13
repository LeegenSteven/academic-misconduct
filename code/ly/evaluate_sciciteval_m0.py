"""Evaluate a SciCiteVal Dev M0 JSONL against the frozen gold/input files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


LABELS = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    predictions = load_jsonl(args.predictions)
    gold_rows = load_jsonl(args.gold)
    input_rows = load_jsonl(args.inputs)
    gold = {str(row["sample_id"]): row["project_label"] for row in gold_rows}
    inputs = {str(row["claim_id"]): row for row in input_rows}

    if len(predictions) != len(gold) or {str(row["claim_id"]) for row in predictions} != set(gold):
        raise ValueError("prediction IDs do not exactly match gold IDs")

    matrix = {gold_label: {pred_label: 0 for pred_label in LABELS} for gold_label in LABELS}
    invalid_evidence_ids: list[str] = []
    model_names = Counter()
    failures = Counter()

    for row in predictions:
        claim_id = str(row["claim_id"])
        predicted = row["label"]
        if predicted not in LABELS:
            raise ValueError(f"invalid label for claim {claim_id}: {predicted!r}")
        matrix[gold[claim_id]][predicted] += 1
        model_names[str(row.get("model_name", "<missing>"))] += 1
        failure = row.get("failure_status")
        failures["null" if failure is None else str(failure)] += 1
        allowed = set(inputs[claim_id].get("allowed_evidence_ids") or [])
        evidence_ids = row.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not set(map(str, evidence_ids)).issubset(allowed):
            invalid_evidence_ids.append(claim_id)

    per_class: dict[str, dict[str, float]] = {}
    for label in LABELS:
        true_positive = matrix[label][label]
        predicted_total = sum(matrix[gold_label][label] for gold_label in LABELS)
        actual_total = sum(matrix[label].values())
        precision = true_positive / predicted_total if predicted_total else 0.0
        recall = true_positive / actual_total if actual_total else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1(precision, recall),
        }

    total = len(predictions)
    correct = sum(matrix[label][label] for label in LABELS)
    result = {
        "task": "SciCiteVal Dev54 Qwen3.8 M0",
        "status": "completed_prerun_gguf",
        "num_claims": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(per_class[label]["f1"] for label in LABELS) / len(LABELS),
        "confusion_matrix": matrix,
        "per_class": per_class,
        "failure_status_counts": dict(failures),
        "claims_with_invalid_evidence_ids": invalid_evidence_ids,
        "model_name_counts": dict(model_names),
        "note": "Original output and retry output are retained on A100. Official GGUF base provenance remains unverified.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
