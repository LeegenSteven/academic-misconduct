"""Evaluate MultiVerS predictions with the official SciFact scoring rules.

This is a self-contained copy of the public scifact-evaluator logic, adapted
only to print a compact, reproducible result record.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter


def load_jsonl(path):
    with open(path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def safe_divide(num, denom):
    return 0.0 if denom == 0 else num / denom


def compute_f1(gold, retrieved, correct, title):
    precision = safe_divide(correct, retrieved)
    recall = safe_divide(correct, gold)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    return {
        f"{title}_precision": precision,
        f"{title}_recall": recall,
        f"{title}_f1": f1,
    }


def unify_label(gold):
    evidence = {}
    for doc, entries in gold.get("evidence", {}).items():
        labels = [entry["label"] for entry in entries]
        if len(set(labels)) > 1:
            raise ValueError(f"Conflicting labels for claim {gold['id']}, document {doc}")
        evidence[str(doc)] = {
            "label": labels[0],
            "rationales": [entry["sentences"] for entry in entries],
        }
    return {"id": gold["id"], "evidence": evidence}


def contains_evidence(gold_rationales, predicted):
    predicted = set(predicted)
    return any(set(rationale).issubset(predicted) for rationale in gold_rationales)


def count_rationale_sents(gold_rationales, predicted):
    correct = 0
    predicted = set(predicted)
    for sentence_id in predicted:
        matching = [rationale for rationale in gold_rationales if sentence_id in rationale]
        if len(matching) > 1:
            raise ValueError("A sentence occurs in more than one gold rationale set")
        if matching and set(matching[0]).issubset(predicted):
            correct += 1
    return correct


def evaluate(golds, preds):
    golds = [unify_label(entry) for entry in golds]
    if [x["id"] for x in golds] != [x["id"] for x in preds]:
        raise ValueError("Prediction claim IDs do not match gold claim IDs or ordering")

    abstract = Counter()
    sentence = Counter()
    allowed = {"SUPPORT", "CONTRADICT", "SUPPORTS", "REFUTES"}
    for gold, pred in zip(golds, preds):
        abstract["relevant"] += len(gold["evidence"])
        for gold_doc in gold["evidence"].values():
            sentence["relevant"] += sum(len(x) for x in gold_doc["rationales"])

        for doc_id, doc_pred in pred.get("evidence", {}).items():
            label = doc_pred["label"]
            if label not in allowed:
                raise ValueError(f"Unallowed predicted label: {label}")
            abstract["retrieved"] += 1
            if str(doc_id) not in gold["evidence"]:
                sentence["retrieved"] += len(doc_pred.get("sentences", []))
                continue

            gold_doc = gold["evidence"][str(doc_id)]
            normalized_pred = {"SUPPORTS": "SUPPORT", "REFUTES": "CONTRADICT"}.get(label, label)
            correct_label = normalized_pred == gold_doc["label"]
            if correct_label:
                abstract["correct_label_only"] += 1
                max_abstract_sents = max(3, min(len(r) for r in gold_doc["rationales"]))
                if contains_evidence(gold_doc["rationales"], doc_pred.get("sentences", [])[:max_abstract_sents]):
                    abstract["correct_rationalized"] += 1

            predicted_sents = doc_pred.get("sentences", [])
            sentence["retrieved"] += len(predicted_sents)
            correct_sents = count_rationale_sents(gold_doc["rationales"], predicted_sents)
            sentence["correct_selection"] += correct_sents
            if correct_label:
                sentence["correct_label"] += correct_sents

    result = {}
    result.update(compute_f1(abstract["relevant"], abstract["retrieved"], abstract["correct_label_only"], "abstract_label_only"))
    result.update(compute_f1(abstract["relevant"], abstract["retrieved"], abstract["correct_rationalized"], "abstract_rationalized"))
    result.update(compute_f1(sentence["relevant"], sentence["retrieved"], sentence["correct_selection"], "sentence_selection"))
    result.update(compute_f1(sentence["relevant"], sentence["retrieved"], sentence["correct_label"], "sentence_label"))
    result["counts"] = {"abstract": dict(abstract), "sentence": dict(sentence)}
    result["num_claims"] = len(golds)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels_file", required=True)
    parser.add_argument("--preds_file", required=True)
    parser.add_argument("--metrics_output_file", default="metrics_scifact_dev.json")
    args = parser.parse_args()
    result = evaluate(load_jsonl(args.labels_file), load_jsonl(args.preds_file))
    with open(args.metrics_output_file, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    for key, value in result.items():
        if key not in {"counts"}:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
