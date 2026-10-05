"""Re-score an existing Qwen3 Dev JSONL against the repaired Sarol gold.

This script performs no model inference. It is deliberately separate from the
future A100 run so that a historical/previous Dev output cannot be presented as
a new experiment. It validates IDs and labels before calculating metrics, keeps
the model's self-reported confidence separate from calibrated scores, and
exports focused error cases for review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


LABELS = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(value)
    return rows


def as_key(value: Any) -> str:
    return str(value)


def ensure_unique(rows: list[dict[str, Any]], field: str, source: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        key = as_key(row.get(field))
        if key in indexed:
            duplicates.append(key)
        indexed[key] = row
    if duplicates:
        raise ValueError(f"Duplicate {field} values in {source}: {sorted(set(duplicates))}")
    return indexed


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def class_metrics(matrix: dict[str, dict[str, int]], label: str) -> dict[str, float]:
    tp = matrix[label][label]
    predicted = sum(matrix[gold][label] for gold in LABELS)
    actual = sum(matrix[label][pred] for pred in LABELS)
    precision = tp / predicted if predicted else 0.0
    recall = tp / actual if actual else 0.0
    return {"precision": precision, "recall": recall, "f1": f1(precision, recall)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--model-inputs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    predictions = ensure_unique(load_jsonl(args.predictions), "claim_id", "predictions")
    claims = ensure_unique(load_jsonl(args.claims), "id", "claims")
    model_inputs = ensure_unique(load_jsonl(args.model_inputs), "claim_id", "model_inputs")
    with args.gold.open(encoding="utf-8-sig", newline="") as stream:
        gold_rows = list(csv.DictReader(stream))
    gold = ensure_unique(gold_rows, "claim_id", "gold")

    expected = set(gold)
    for name, indexed in (("predictions", predictions), ("claims", claims), ("model_inputs", model_inputs)):
        if set(indexed) != expected:
            missing = sorted(expected - set(indexed))
            extra = sorted(set(indexed) - expected)
            raise ValueError(f"{name} IDs do not match gold; missing={missing[:10]}, extra={extra[:10]}")

    matrix = {gold_label: {pred_label: 0 for pred_label in LABELS} for gold_label in LABELS}
    predicted_counts = Counter()
    failure_counts = Counter()
    model_counts = Counter()
    malformed_evidence_ids: list[str] = []
    out_rows: list[dict[str, Any]] = []

    for claim_id in sorted(expected, key=lambda value: int(value)):
        pred = predictions[claim_id]
        gold_label = gold[claim_id].get("project_label")
        pred_label = pred.get("label")
        if gold_label not in LABELS:
            raise ValueError(f"Invalid gold label for {claim_id}: {gold_label!r}")
        if pred_label not in LABELS:
            raise ValueError(f"Invalid prediction label for {claim_id}: {pred_label!r}")
        matrix[gold_label][pred_label] += 1
        predicted_counts[pred_label] += 1
        failure = pred.get("failure_status")
        failure_counts["null" if failure is None else str(failure)] += 1
        model_counts[str(pred.get("model_name", "<missing>"))] += 1

        evidence_ids = pred.get("evidence_ids")
        allowed = set(model_inputs[claim_id].get("allowed_evidence_ids") or [])
        bad_ids: list[str] = []
        if not isinstance(evidence_ids, list):
            bad_ids = ["<not-a-list>"]
            evidence_ids = []
        else:
            bad_ids = sorted({str(item) for item in evidence_ids} - allowed)
        if bad_ids:
            malformed_evidence_ids.append(claim_id)

        if pred_label != gold_label:
            focus = "NOT_ACCURATE_misclassified" if gold_label == "NOT_ACCURATE" and pred_label in {"ACCURATE", "IRRELEVANT"} else "other_label_mismatch"
            out_rows.append(
                {
                    "claim_id": claim_id,
                    "focus": focus,
                    "gold_label": gold_label,
                    "predicted_label": pred_label,
                    "claim": claims[claim_id].get("claim", ""),
                    "evidence_ids": json.dumps(evidence_ids, ensure_ascii=False),
                    "invalid_evidence_ids": json.dumps(bad_ids, ensure_ascii=False),
                    "reason": pred.get("reason", ""),
                    "confidence": pred.get("confidence"),
                    "failure_status": failure,
                    "model_name": pred.get("model_name"),
                }
            )

    total = len(expected)
    correct = sum(matrix[label][label] for label in LABELS)
    per_class = {label: class_metrics(matrix, label) for label in LABELS}
    metrics = {
        "task": "Sarol Dev Qwen3 existing-output reanalysis",
        "status": "reanalysis_completed_no_new_inference",
        "data_version": "sarol-quality-v1",
        "num_claims": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(per_class[label]["f1"] for label in LABELS) / len(LABELS),
        "gold_counts": {label: sum(matrix[label].values()) for label in LABELS},
        "predicted_counts": dict(predicted_counts),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "failure_status_counts": dict(failure_counts),
        "model_name_counts": dict(model_counts),
        "evidence_id_validation": {
            "claims_with_out_of_range_ids": len(malformed_evidence_ids),
            "claim_ids": malformed_evidence_ids,
            "note": "This is an input/evidence-ID check; label metrics are computed from labels only.",
        },
        "confidence_note": "confidence is retained as self-reported confidence; no calibrated score_* fields are produced.",
        "limitation": "This is a re-score of an existing Dev output, not a new inference under a newly frozen A100 configuration.",
    }

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics_reanalysis.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_rows.sort(key=lambda row: (0 if row["focus"] == "NOT_ACCURATE_misclassified" else 1, int(row["claim_id"])))
    error_fields = list(out_rows[0]) if out_rows else [
        "claim_id", "focus", "gold_label", "predicted_label", "claim", "evidence_ids",
        "invalid_evidence_ids", "reason", "confidence", "failure_status", "model_name",
    ]
    with (output_dir / "error_cases.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=error_fields)
        writer.writeheader()
        writer.writerows(out_rows)

    manifest = {
        "manifest_version": "qwen3_dev_reanalysis_v1",
        "status": "completed_reanalysis_only",
        "new_model_inference_performed": False,
        "data_version": "sarol-quality-v1",
        "records": total,
        "source_files": {
            "existing_qwen3_dev_predictions": {"path_hint": "成员2_本周任务_2026-09-17/03_大模型/runs/sarol316_qwen3/model_outputs_final.jsonl", "sha256": sha256(args.predictions)},
            "gold_mapping_dev": {"repo_path": "data/quality_v1/sarol/gold_mapping-dev.csv", "sha256": sha256(args.gold)},
            "claims_dev_model": {"repo_path": "data/quality_v1/sarol/claims-dev-model.jsonl", "sha256": sha256(args.claims)},
            "historical_model_inputs_dev316": {"path_hint": "成员2_本周任务_2026-09-17/03_大模型/model_inputs_dev316.jsonl", "sha256": sha256(args.model_inputs)},
        },
        "blocking_for_final_experiment": [
            "A100 execution of a newly frozen Dev configuration",
            "model/checkpoint digest and runtime log",
            "new Dev raw output before locking the Test configuration",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": metrics["status"], "num_claims": total, "accuracy": metrics["accuracy"], "macro_f1": metrics["macro_f1"], "error_cases": len(out_rows), "priority_errors": sum(row["focus"] == "NOT_ACCURATE_misclassified" for row in out_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
