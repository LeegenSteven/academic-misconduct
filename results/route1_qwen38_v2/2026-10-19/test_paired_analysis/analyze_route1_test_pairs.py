"""Audit and pair the frozen route1 v2 Test predictions without model inference.

The join key is (dataset, claim_id).  This script does not change any
prediction, gold label, checkpoint, or Test configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")
DATASETS = ("sciciteval", "sarol")
MODELS = ("M0", "Mbio", "Mscv")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def index_unique(rows: list[dict], key: str, source: Path) -> dict[str, dict]:
    result = {}
    for row in rows:
        claim_id = str(row[key])
        if claim_id in result:
            raise ValueError(f"duplicate {key}={claim_id}: {source}")
        result[claim_id] = row
    return result


def f1_macro(gold: list[str], preds: list[str]) -> float:
    scores = []
    for label in LABELS:
        tp = sum(g == p == label for g, p in zip(gold, preds))
        fp = sum(g != label and p == label for g, p in zip(gold, preds))
        fn = sum(g == label and p != label for g, p in zip(gold, preds))
        denom = 2 * tp + fp + fn
        scores.append(2 * tp / denom if denom else 0.0)
    return sum(scores) / len(scores)


def load_domain(repo: Path, run: Path, domain: str) -> tuple[list[dict], dict]:
    data_dir = repo / "results/route1_qwen38_v2/2026-10-15" / domain
    input_path = data_dir / "test.inputs.jsonl"
    gold_path = data_dir / "test.gold.jsonl"
    inputs = jsonl(input_path)
    gold = jsonl(gold_path)
    if len(inputs) != len(gold):
        raise ValueError(f"input/gold length mismatch: {domain}")
    input_ids = [str(row["claim_id"]) for row in inputs]
    gold_ids = [str(row["claim_id"]) for row in gold]
    if input_ids != gold_ids or len(set(input_ids)) != len(input_ids):
        raise ValueError(f"input/gold ID or order mismatch: {domain}")
    gold_labels = [row.get("label") for row in gold]
    if set(gold_labels) - set(LABELS):
        raise ValueError(f"unknown gold label: {domain}")

    prediction_by_model = {}
    metric_by_model = {}
    file_hashes = {"inputs": sha256(input_path), "gold": sha256(gold_path)}
    for model in MODELS:
        unit = run / "test" / domain / model
        pred_path = unit / f"{model}_test_predictions.jsonl"
        metric_path = unit / f"{model}_test_metrics.json"
        preds = jsonl(pred_path)
        metric = json.loads(metric_path.read_text(encoding="utf-8"))
        ids = [str(row["claim_id"]) for row in preds]
        if ids != gold_ids:
            raise ValueError(f"prediction IDs/order mismatch: {domain}/{model}")
        for row, label in zip(preds, gold_labels):
            if row["gold"] != label:
                raise ValueError(f"prediction gold mismatch: {domain}/{model}/{row['claim_id']}")
            if row["pred"] not in LABELS and row["pred"] != "INVALID":
                raise ValueError(f"unknown predicted label: {domain}/{model}/{row['claim_id']}")
        pred_hash = sha256(pred_path)
        if pred_hash != metric["prediction_sha256"]:
            raise ValueError(f"prediction hash mismatch: {domain}/{model}")
        if metric["inputs_sha256"] != file_hashes["inputs"] or metric["gold_sha256"] != file_hashes["gold"]:
            raise ValueError(f"input/gold hash mismatch: {domain}/{model}")
        if (metric.get("max_length"), metric.get("max_new_tokens"), metric.get("enable_thinking"), metric.get("retry_count")) != (5120, 512, False, 0):
            raise ValueError(f"inference configuration mismatch: {domain}/{model}")
        if (metric.get("adapter") is None) != (model == "M0"):
            raise ValueError(f"adapter presence mismatch: {domain}/{model}")
        correct = sum(row["pred"] == label for row, label in zip(preds, gold_labels))
        macro = f1_macro(gold_labels, [row["pred"] for row in preds])
        if correct != metric["correct"] or abs(correct / len(gold) - metric["accuracy"]) > 1e-12:
            raise ValueError(f"accuracy mismatch: {domain}/{model}")
        if abs(macro - metric["macro_f1"]) > 1e-12:
            raise ValueError(f"macro-F1 mismatch: {domain}/{model}")
        invalid = sum(row["pred"] == "INVALID" or row.get("invalid_reason") is not None for row in preds)
        if invalid != metric["invalid_count"]:
            raise ValueError(f"invalid count mismatch: {domain}/{model}")
        prediction_by_model[model] = preds
        metric_by_model[model] = metric
        file_hashes[f"{model}_predictions"] = pred_hash
        file_hashes[f"{model}_metrics"] = sha256(metric_path)

    paired = []
    for idx, (source, reference) in enumerate(zip(inputs, gold)):
        preds = {model: prediction_by_model[model][idx]["pred"] for model in MODELS}
        paired.append({
            "dataset": domain,
            "claim_id": str(reference["claim_id"]),
            "gold": reference["label"],
            "predictions": preds,
            "correct": {model: preds[model] == reference["label"] for model in MODELS},
            "invalid_reason": {model: prediction_by_model[model][idx].get("invalid_reason") for model in MODELS},
            "source_input_sha256": source.get("input_sha256"),
        })
    return paired, {"files": file_hashes, "metrics": metric_by_model, "records": len(paired)}


def compare(paired: list[dict], adapter: str, metrics: dict) -> dict:
    counts = Counter()
    by_gold = defaultdict(Counter)
    transitions = defaultdict(Counter)
    examples = defaultdict(list)
    for row in paired:
        base_ok = row["correct"]["M0"]
        adapt_ok = row["correct"][adapter]
        status = (
            "both_correct" if base_ok and adapt_ok else
            "new_error" if base_ok else
            "repaired_error" if adapt_ok else
            "both_wrong"
        )
        counts[status] += 1
        by_gold[row["gold"]][status] += 1
        transitions[row["predictions"]["M0"]][row["predictions"][adapter]] += 1
        examples[status].append(row["claim_id"])
    base = metrics["M0"]
    updated = metrics[adapter]
    if sum(counts.values()) != len(paired):
        raise ValueError(f"pair outcome count mismatch: {adapter}")
    if counts["both_correct"] + counts["new_error"] != base["correct"]:
        raise ValueError(f"M0 correct count mismatch: {adapter}")
    if counts["both_correct"] + counts["repaired_error"] != updated["correct"]:
        raise ValueError(f"adapter correct count mismatch: {adapter}")
    return {
        "adapter": adapter,
        "baseline": "M0",
        "records": len(paired),
        "outcome_counts": dict(counts),
        "net_correct_change": counts["repaired_error"] - counts["new_error"],
        "accuracy": {"M0": base["accuracy"], adapter: updated["accuracy"], "delta_percentage_points": 100 * (updated["accuracy"] - base["accuracy"])},
        "macro_f1": {"M0": base["macro_f1"], adapter: updated["macro_f1"], "delta": updated["macro_f1"] - base["macro_f1"]},
        "gold_label_by_outcome": {label: dict(by_gold[label]) for label in LABELS},
        "prediction_transition_matrix": {label: dict(transitions[label]) for label in (*LABELS, "INVALID")},
        "specific_new_errors": {
            "gold_accurate_changed_to_other": sum(
                row["gold"] == "ACCURATE" and row["correct"]["M0"] and not row["correct"][adapter]
                for row in paired
            ),
            "gold_nonaccurate_changed_to_accurate": sum(
                row["gold"] != "ACCURATE" and row["correct"]["M0"] and row["predictions"][adapter] == "ACCURATE"
                for row in paired
            ),
        },
        "example_ids_by_outcome": {key: values[:20] for key, values in examples.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    repo, run, out = (path.resolve() for path in (args.repo_root, args.run_root, args.out_dir))
    out.mkdir(parents=True, exist_ok=True)

    all_paired = []
    report = {"scope": "frozen route1 v2 classification Test, paired by (dataset, claim_id)",
              "max_length": 5120, "max_new_tokens": 512,
              "no_model_run": True, "no_checkpoint_selection": True,
              "datasets": {}}
    for domain in DATASETS:
        paired, metadata = load_domain(repo, run, domain)
        all_paired.extend(paired)
        report["datasets"][domain] = {
            "records": metadata["records"],
            "files": metadata["files"],
            "model_metrics": {model: {
                "accuracy": metadata["metrics"][model]["accuracy"],
                "macro_f1": metadata["metrics"][model]["macro_f1"],
                "correct": metadata["metrics"][model]["correct"],
                "invalid_count": metadata["metrics"][model]["invalid_count"],
            } for model in MODELS},
            "comparisons": {adapter: compare(paired, adapter, metadata["metrics"]) for adapter in ("Mbio", "Mscv")},
        }

    (out / "paired_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (out / "paired_rows.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in all_paired:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"paired_samples={len(all_paired)} units={len(DATASETS) * len(MODELS)}")
    for domain in DATASETS:
        for adapter in ("Mbio", "Mscv"):
            item = report["datasets"][domain]["comparisons"][adapter]
            print(domain, adapter, item["outcome_counts"],
                  "accuracy_delta_pp=", round(item["accuracy"]["delta_percentage_points"], 4),
                  "macro_f1_delta=", round(item["macro_f1"]["delta"], 6))


if __name__ == "__main__":
    main()
