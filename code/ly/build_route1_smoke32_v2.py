#!/usr/bin/env python3
"""Select deterministic 32-record GPU smoke inputs from each v2 Train only.

The output is an engineering smoke sample, never a checkpoint-selection set or
a formal scored benchmark. Only Train inputs and gold sidecars are opened.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")
DATASETS = ("sciciteval", "sarol")
LOGICAL_ROOT = "results/route1_qwen38_v2/2026-10-15"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_lines(path: Path) -> tuple[bytes, list[bytes], list[dict]]:
    raw = path.read_bytes()
    lines = [line for line in raw.splitlines(keepends=True) if line.strip()]
    rows = [json.loads(line.decode("utf-8-sig")) for line in lines]
    if any(not line.endswith(b"\n") for line in lines):
        raise ValueError(f"Source JSONL records must end in newline: {path.name}")
    return raw, lines, rows


def prompt_digest(row: dict) -> str:
    payload = {"system_prompt": row["system_prompt"], "user_prompt": row["user_prompt"]}
    return digest(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8"))


def build_one(data_root: Path, dataset: str) -> dict:
    folder = data_root / dataset
    input_path, gold_path = folder / "train.inputs.jsonl", folder / "train.gold.jsonl"
    input_raw, input_lines, inputs = load_lines(input_path)
    gold_raw, gold_lines, gold = load_lines(gold_path)
    if len(inputs) != len(gold) or len(inputs) < 32:
        raise ValueError(f"Train/gold must align and contain at least 32 records: {dataset}")
    ids = [row["claim_id"] for row in inputs]
    if len(ids) != len(set(ids)) or ids != [row["claim_id"] for row in gold]:
        raise ValueError(f"Train/gold IDs are duplicated or out of order: {dataset}")
    if any(row["label"] not in LABELS for row in gold):
        raise ValueError(f"Unknown Train label: {dataset}")
    if any(row["input_sha256"] != prompt_digest(row) for row in inputs):
        raise ValueError(f"Train model-prompt hash mismatch: {dataset}")

    chosen: set[int] = set()
    class_stage = {}
    for label in LABELS:
        positions = [i for i, row in enumerate(gold) if row["label"] == label][:2]
        if len(positions) != 2:
            raise ValueError(f"Train must contain at least two examples of {label}: {dataset}")
        chosen.update(positions)
        class_stage[label] = [ids[i] for i in positions]

    lengths = [len(row["system_prompt"]) + len(row["user_prompt"]) for row in inputs]
    longest = sorted(range(len(inputs)), key=lambda i: (-lengths[i], i))[:4]
    longest_new = [i for i in longest if i not in chosen]
    chosen.update(longest)
    fill = []
    for i in range(len(inputs)):
        if len(chosen) == 32:
            break
        if i not in chosen:
            chosen.add(i)
            fill.append(i)
    positions = sorted(chosen)
    if len(positions) != 32:
        raise ValueError(f"Expected exactly 32 smoke records: {dataset}")
    selected_inputs = [inputs[i] for i in positions]
    selected_gold = [gold[i] for i in positions]
    distribution = Counter(row["label"] for row in selected_gold)
    if any(distribution[label] < 2 for label in LABELS):
        raise ValueError(f"Smoke sample lost class coverage: {dataset}")

    output_info = {}
    for name, lines, expected_rows in (
        ("smoke32.inputs.jsonl", input_lines, selected_inputs),
        ("smoke32.gold.jsonl", gold_lines, selected_gold),
    ):
        # Copy complete source lines byte-for-byte, including JSON formatting.
        raw = b"".join(lines[i] for i in positions)
        path = folder / name
        path.write_bytes(raw)
        actual_rows = [json.loads(line.decode("utf-8-sig")) for line in raw.splitlines() if line.strip()]
        if actual_rows != expected_rows or path.read_bytes() != raw:
            raise ValueError(f"Smoke output changed a source record: {dataset}/{name}")
        output_info[name] = {"path": f"{LOGICAL_ROOT}/{dataset}/{name}",
                             "records": len(actual_rows), "bytes": len(raw), "sha256": digest(raw)}
    manifest = {
        "manifest_version": "route1_smoke32_v2_2026-10-15",
        "dataset": dataset,
        "status": "generated_static_input_only_no_gpu_run",
        "purpose": "GPU/input engineering smoke only: load model, forward/backward/optimizer step, save/reload adapter, then inference",
        "not_for": ["checkpoint selection", "hyperparameter selection", "formal accuracy/F1 reporting"],
        "source_split": "train",
        "dev_or_test_files_opened": False,
        "selection_rule": "Union first 2 Train records per class, global top 4 Train records by len(system_prompt)+len(user_prompt) (skip duplicates), then earliest unselected Train records until 32; output in original Train order",
        "prompt_length_unit": "Python len(str) Unicode code points; system and user only; character length is not a tokenizer length estimate",
        "length_tie_break": "original Train order",
        "first_two_per_class_ids": class_stage,
        "four_longest_train_candidates": [{"claim_id": ids[i], "prompt_characters": lengths[i]} for i in longest],
        "new_ids_from_longest_stage": [ids[i] for i in longest_new],
        "fill_ids_in_train_order": [ids[i] for i in fill],
        "selected_source_positions_zero_based": positions,
        "selected_claim_ids_in_output_order": [ids[i] for i in positions],
        "join_key_policy": "(dataset, source_split, claim_id); smoke32 is a Train subset, not an independent split",
        "label_distribution": dict(sorted(distribution.items())),
        "sources": {
            "inputs": {"path": f"{LOGICAL_ROOT}/{dataset}/train.inputs.jsonl", "records": len(inputs),
                       "bytes": len(input_raw), "sha256": digest(input_raw)},
            "gold": {"path": f"{LOGICAL_ROOT}/{dataset}/train.gold.jsonl", "records": len(gold),
                     "bytes": len(gold_raw), "sha256": digest(gold_raw)},
        },
        "outputs": output_info,
        "generator": {"path": "code/ly/build_route1_smoke32_v2.py", "sha256": digest(Path(__file__).read_bytes())},
        "validation": {"records": 32, "all_three_classes_covered": True,
                       "input_gold_ids_order_aligned": True,
                       "only_train_source_records_selected": True,
                       "source_record_lines_copied_byte_identically": True,
                       "model_prompt_and_external_metadata_unchanged": True,
                       "no_model_execution": True},
    }
    (folder / "smoke32.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8", newline="\n")
    return {"dataset": dataset, "records": 32, "label_distribution": dict(sorted(distribution.items())),
            "manifest": f"{LOGICAL_ROOT}/{dataset}/smoke32.manifest.json"}


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=repo_root / LOGICAL_ROOT)
    args = parser.parse_args()
    for dataset in DATASETS:
        print(json.dumps(build_one(args.data_root, dataset), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
