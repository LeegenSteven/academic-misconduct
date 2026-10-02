"""Compare Sarol gold-evidence and TF-IDF top-20 predictions fairly.

The comparison is restricted to development claims that have annotated
evidence blocks. Claims without evidence cannot be evaluated in an oracle
evidence setting because there is no gold block to provide to MultiVerS.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ALL_LABELS = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]
EVIDENCE_GOLD_LABELS = ["ACCURATE", "NOT_ACCURATE"]


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def aggregate(prediction):
    labels = {entry.get("label") for entry in prediction.get("evidence", {}).values()}
    if labels & {"CONTRADICT", "REFUTES"}:
        return "NOT_ACCURATE"
    if labels & {"SUPPORT", "SUPPORTS"}:
        return "ACCURATE"
    return "IRRELEVANT"


def class_scores(matrix, label):
    true_positive = matrix[(label, label)]
    predicted = sum(matrix[(gold, label)] for gold in EVIDENCE_GOLD_LABELS)
    gold = sum(matrix[(label, pred)] for pred in ALL_LABELS)
    precision = true_positive / predicted if predicted else 0.0
    recall = true_positive / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def evaluate(name, predictions, mapping, eligible_ids):
    matrix = Counter()
    changed_predictions = Counter()
    for claim_id in sorted(eligible_ids, key=int):
        gold = mapping[claim_id]
        predicted = aggregate(predictions[claim_id])
        matrix[(gold, predicted)] += 1
        changed_predictions[predicted] += 1

    per_class = {label: class_scores(matrix, label) for label in EVIDENCE_GOLD_LABELS}
    correct = sum(matrix[(label, label)] for label in EVIDENCE_GOLD_LABELS)
    total = len(eligible_ids)
    return {
        "name": name,
        "num_claims": total,
        "accuracy": correct / total,
        "macro_f1_over_evidence_gold_classes": sum(
            per_class[label]["f1"] for label in EVIDENCE_GOLD_LABELS
        )
        / len(EVIDENCE_GOLD_LABELS),
        "per_class": per_class,
        "predicted_label_counts": dict(changed_predictions),
        "non_irrelevant_prediction_rate": (
            changed_predictions["ACCURATE"] + changed_predictions["NOT_ACCURATE"]
        )
        / total,
        "confusion_matrix": {
            gold: {pred: matrix[(gold, pred)] for pred in ALL_LABELS}
            for gold in EVIDENCE_GOLD_LABELS
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--oracle-predictions", type=Path, required=True)
    parser.add_argument("--top20-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    claims = load_jsonl(args.claims)
    with args.mapping.open(encoding="utf-8-sig", newline="") as stream:
        mapping_rows = list(csv.DictReader(stream))
    mapping = {str(row["claim_id"]): row["project_label"] for row in mapping_rows}
    oracle = {str(row["id"]): row for row in load_jsonl(args.oracle_predictions)}
    top20 = {str(row["id"]): row for row in load_jsonl(args.top20_predictions)}

    all_ids = {str(row["id"]) for row in claims}
    eligible_ids = {str(row["id"]) for row in claims if row.get("evidence")}
    missing_ids = all_ids - eligible_ids
    for name, values in (("mapping", mapping), ("oracle", oracle), ("top20", top20)):
        if set(values) != all_ids:
            missing = sorted(all_ids - set(values), key=int)
            extra = sorted(set(values) - all_ids, key=int)
            raise ValueError(f"{name} IDs differ from claims; missing={missing[:5]}, extra={extra[:5]}")

    oracle_labels = {claim_id: aggregate(oracle[claim_id]) for claim_id in eligible_ids}
    top20_labels = {claim_id: aggregate(top20[claim_id]) for claim_id in eligible_ids}
    disagreement_ids = sorted(
        [claim_id for claim_id in eligible_ids if oracle_labels[claim_id] != top20_labels[claim_id]],
        key=int,
    )

    result = {
        "task": "Sarol 2024 dev gold-evidence versus TF-IDF top-20 comparison",
        "scope": "Only claims with annotated evidence blocks",
        "all_dev_claims": len(all_ids),
        "evidence_eligible_claims": len(eligible_ids),
        "excluded_no_evidence_claims": len(missing_ids),
        "excluded_label_counts": dict(Counter(mapping[claim_id] for claim_id in missing_ids)),
        "eligible_label_counts": dict(Counter(mapping[claim_id] for claim_id in eligible_ids)),
        "oracle": evaluate("gold_evidence_blocks", oracle, mapping, eligible_ids),
        "top20": evaluate("tfidf_top20_within_cited_paper", top20, mapping, eligible_ids),
        "prediction_disagreement_count": len(disagreement_ids),
        "prediction_disagreement_examples": disagreement_ids[:20],
        "interpretation_note": (
            "IRRELEVANT predictions remain errors on this subset. Macro-F1 is averaged only over "
            "ACCURATE and NOT_ACCURATE because no IRRELEVANT claim has annotated evidence blocks."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
