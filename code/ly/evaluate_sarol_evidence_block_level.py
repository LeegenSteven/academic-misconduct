"""Evaluate Sarol predictions on annotated evidence blocks only.

This avoids claim-level aggregation and treats a missing prediction for a gold
evidence block as MISSING. It is intended to separate classification behavior
from the number of candidate blocks supplied to MultiVerS.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def gold_label(raw_label: str) -> str:
    if raw_label in {"ACCURATE", "INDIRECT", "INDIRECT_NOT_REVIEW"}:
        return "ACCURATE"
    if raw_label == "IRRELEVANT":
        return "IRRELEVANT"
    return "NOT_ACCURATE"


def predicted_label(entry) -> str:
    label = entry.get("label")
    if label in {"SUPPORT", "SUPPORTS"}:
        return "ACCURATE"
    if label in {"CONTRADICT", "REFUTES"}:
        return "NOT_ACCURATE"
    return "MISSING"


def score(matrix, gold_labels, predicted_labels):
    per_class = {}
    for label in ("ACCURATE", "NOT_ACCURATE"):
        tp = matrix[(label, label)]
        pred_total = sum(matrix[(gold, label)] for gold in gold_labels)
        gold_total = sum(matrix[(label, pred)] for pred in predicted_labels)
        precision = tp / pred_total if pred_total else 0.0
        recall = tp / gold_total if gold_total else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1}
    return per_class


def evaluate(name, predictions, gold_blocks):
    matrix = Counter()
    for claim_id, doc_id, gold in gold_blocks:
        doc_predictions = predictions.get(claim_id, {}).get("evidence", {})
        pred_entry = doc_predictions.get(doc_id)
        pred = predicted_label(pred_entry) if pred_entry else "MISSING"
        matrix[(gold, pred)] += 1

    gold_labels = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]
    predicted_labels = ["ACCURATE", "NOT_ACCURATE", "MISSING"]
    per_class = score(matrix, gold_labels, predicted_labels)
    count = len(gold_blocks)
    return {
        "name": name,
        "gold_evidence_blocks": count,
        "gold_label_counts": dict(Counter(gold for _, _, gold in gold_blocks)),
        "predicted_label_counts": dict(Counter(pred for (_, pred), n in matrix.items() for _ in range(n))),
        "missing_rate": sum(matrix[(gold, "MISSING")] for gold in gold_labels) / count,
        "per_class": per_class,
        "macro_f1_over_binary_gold": sum(item["f1"] for item in per_class.values()) / 2,
        "confusion_matrix": {
            gold: {pred: matrix[(gold, pred)] for pred in predicted_labels}
            for gold in gold_labels
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--oracle-predictions", type=Path, required=True)
    parser.add_argument("--top20-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    claims = load_jsonl(args.claims)
    gold_blocks = []
    for claim in claims:
        for doc_id, entries in claim.get("evidence", {}).items():
            raw_labels = {entry["label"] for entry in entries}
            if len(raw_labels) != 1:
                raise ValueError(f"Conflicting labels for claim={claim['id']} doc={doc_id}: {raw_labels}")
            gold_blocks.append((str(claim["id"]), str(doc_id), gold_label(next(iter(raw_labels)))))

    oracle_rows = {str(row["id"]): row for row in load_jsonl(args.oracle_predictions)}
    top20_rows = {str(row["id"]): row for row in load_jsonl(args.top20_predictions)}
    result = {
        "task": "Sarol 2024 evidence-block classification comparison",
        "scope": "All annotated evidence blocks; missing predictions are counted as MISSING",
        "gold_evidence_blocks": len(gold_blocks),
        "oracle": evaluate("gold_evidence_blocks_input", oracle_rows, gold_blocks),
        "top20": evaluate("tfidf_top20_input", top20_rows, gold_blocks),
        "note": "This is a block-level diagnostic, not the official claim-level three-class score.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
