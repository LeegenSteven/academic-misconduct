from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


LABELS = ["Correct", "Incorrect", "Unrelated"]


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def f1(tp: int, predicted: int, gold: int):
    precision = tp / predicted if predicted else 0.0
    recall = tp / gold if gold else 0.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": score}


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, default=root / "sciciteval_transfer_input" / "mapping.csv")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=root / "sciciteval_transfer_results.json")
    parser.add_argument("--confusion-output", type=Path, default=root / "sciciteval_transfer_confusion.csv")
    args = parser.parse_args()

    with args.mapping.open(encoding="utf-8-sig", newline="") as stream:
        mapping = list(csv.DictReader(stream))
    predictions = load_jsonl(args.predictions)
    pred_by_id = {str(row["id"]): row for row in predictions}
    if len(pred_by_id) != len(mapping):
        raise ValueError(f"Prediction count {len(pred_by_id)} does not match mapping count {len(mapping)}")

    matrix = Counter()
    rationale_nonempty = 0
    for row in mapping:
        row_id = row["row_id"]
        gold_label = row["gold_label"]
        prediction = pred_by_id[row_id]
        evidence = prediction.get("evidence", {})
        doc_id = row["doc_id"]
        doc_prediction = evidence.get(str(doc_id)) or evidence.get(doc_id)
        if doc_prediction is None:
            predicted_label = "Unrelated"
        else:
            predicted_label = {
                "SUPPORT": "Correct",
                "SUPPORTS": "Correct",
                "CONTRADICT": "Incorrect",
                "REFUTES": "Incorrect",
            }.get(doc_prediction.get("label"), "Unrelated")
            rationale_nonempty += int(bool(doc_prediction.get("sentences")))
        matrix[(gold_label, predicted_label)] += 1

    total = len(mapping)
    correct = sum(matrix[(label, label)] for label in LABELS)
    per_class = {}
    for label in LABELS:
        tp = matrix[(label, label)]
        pred_total = sum(matrix[(other, label)] for other in LABELS)
        gold_total = sum(matrix[(label, other)] for other in LABELS)
        per_class[label] = f1(tp, pred_total, gold_total)
    metrics = {
        "task": "SciCiteVal cross-dataset transfer with MultiVerS",
        "prediction_file": str(args.predictions),
        "num_rows": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(per_class[label]["f1"] for label in LABELS) / len(LABELS),
        "per_class": per_class,
        "rationale_nonempty_rate": rationale_nonempty / total if total else 0.0,
        "protocol": "Correct->SUPPORT, Incorrect->CONTRADICT, Unrelated->NEI; evidence text was given and sentence-level gold offsets were unavailable.",
        "confusion_matrix": {gold: {pred: matrix[(gold, pred)] for pred in LABELS} for gold in LABELS},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.confusion_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["gold/predicted"] + LABELS)
        for gold in LABELS:
            writer.writerow([gold] + [matrix[(gold, pred)] for pred in LABELS])
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
