from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


LABELS = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def score(tp, predicted, gold):
    precision = tp / predicted if predicted else 0.0
    recall = tp / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def aggregate(prediction):
    labels = {entry.get("label") for entry in prediction.get("evidence", {}).values()}
    if labels & {"CONTRADICT", "REFUTES"}:
        return "NOT_ACCURATE"
    if labels & {"SUPPORT", "SUPPORTS"}:
        return "ACCURATE"
    return "IRRELEVANT"


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confusion-output", type=Path, required=True)
    args = parser.parse_args()

    with args.mapping.open(encoding="utf-8-sig", newline="") as stream:
        mapping = list(csv.DictReader(stream))
    predictions = {str(row["id"]): row for row in load_jsonl(args.predictions)}
    if len(predictions) != len(mapping):
        raise ValueError(f"Prediction count {len(predictions)} != mapping count {len(mapping)}")

    matrix = Counter()
    conflicts = 0
    for row in mapping:
        pred = predictions[row["claim_id"]]
        raw_labels = {entry.get("label") for entry in pred.get("evidence", {}).values()}
        conflicts += int(bool(raw_labels & {"CONTRADICT", "REFUTES"}) and bool(raw_labels & {"SUPPORT", "SUPPORTS"}))
        matrix[(row["project_label"], aggregate(pred))] += 1

    total = len(mapping)
    per_class = {}
    for label in LABELS:
        tp = matrix[(label, label)]
        pred_total = sum(matrix[(gold, label)] for gold in LABELS)
        gold_total = sum(matrix[(label, pred)] for pred in LABELS)
        per_class[label] = score(tp, pred_total, gold_total)
    accuracy = sum(matrix[(label, label)] for label in LABELS) / total
    result = {
        "task": "Sarol 2024 dev cross-dataset transfer with SciFact MultiVerS checkpoint",
        "num_claims": total,
        "accuracy": accuracy,
        "macro_f1": sum(per_class[label]["f1"] for label in LABELS) / len(LABELS),
        "per_class": per_class,
        "prediction_conflicts": conflicts,
        "aggregation_protocol": "NOT_ACCURATE if any CONTRADICT; else ACCURATE if any SUPPORT; else IRRELEVANT",
        "confusion_matrix": {gold: {pred: matrix[(gold, pred)] for pred in LABELS} for gold in LABELS},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.confusion_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["gold/predicted"] + LABELS)
        for gold in LABELS:
            writer.writerow([gold] + [matrix[(gold, pred)] for pred in LABELS])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
