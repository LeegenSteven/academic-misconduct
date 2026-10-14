#!/usr/bin/env python3
"""Build SciCiteVal Train inputs using the frozen route1 v1 prompt contract.

The source is the frozen experiment_dataset.tsv.  Each supplied Cited_content
passage is represented as one evidence slot D01:S01, matching the Dev M0
builder.  Gold labels and split names remain in the split CSV only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

REQUIRED_SOURCE_FIELDS = {"Citation_context", "Cited_content"}
REQUIRED_REFERENCE_FIELDS = {"system_prompt", "user_prompt"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    missing = REQUIRED_SOURCE_FIELDS - set(rows[0]) if rows else REQUIRED_SOURCE_FIELDS
    if missing:
        raise ValueError(f"Source TSV missing fields: {sorted(missing)}")
    return rows


def load_split(path: Path) -> dict[int, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapping: dict[int, dict[str, str]] = {}
    for row in rows:
        row_id = int(row["row_id"])
        if row_id in mapping:
            raise ValueError(f"Duplicate row_id in split CSV: {row_id}")
        mapping[row_id] = row
    return mapping


def load_system_prompt(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        first = next((json.loads(line) for line in handle if line.strip()), None)
    if not first or not first.get("system_prompt"):
        raise ValueError(f"Prompt reference has no system_prompt: {path}")
    return first["system_prompt"]


def make_record(row_id: int, source: dict[str, str], system_prompt: str) -> dict:
    context = source["Citation_context"]
    cited = source["Cited_content"]
    return {
        "claim_id": row_id,
        "system_prompt": system_prompt,
        "user_prompt": (
            f"claim_id: {row_id}\n"
            f"施引上下文：{context}\n"
            "被引内容：\n"
            f"D01:S01 | {cited}\n"
            "请只输出符合要求的 JSON。"
        ),
        "allowed_evidence_ids": ["D01:S01"],
        "candidate_evidence": [
            {"evidence_id": "D01:S01", "text": cited, "locator": "cited_content"}
        ],
        "input_warning": "SciCiteVal replay input; D01:S01 is the supplied Cited_content passage.",
        "sample_id": row_id,
        "input_sha256": hashlib.sha256((context + "\n" + cited).encode("utf-8")).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-tsv", required=True, type=Path)
    parser.add_argument("--split-csv", required=True, type=Path)
    parser.add_argument("--prompt-reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    source_rows = load_tsv(args.experiment_tsv)
    split_rows = load_split(args.split_csv)
    system_prompt = load_system_prompt(args.prompt_reference)
    if len(source_rows) != len(split_rows):
        raise ValueError(f"Source/split row count mismatch: {len(source_rows)} != {len(split_rows)}")

    selected: list[dict] = []
    for row_id, source in enumerate(source_rows):
        split = split_rows[row_id]
        if split["split"] != "train":
            continue
        if split["group_key"].startswith("conflict"):
            raise ValueError(f"Conflict row entered train: {row_id}")
        selected.append(make_record(row_id, source, system_prompt))

    if len(selected) != 713:
        raise ValueError(f"Expected 713 train records, got {len(selected)}")
    ids = [int(row["claim_id"]) for row in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate claim_id in generated train records")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "task": "SciCiteVal Train713 Qwen3.8 adapter preparation",
        "status": "prepared_training_input",
        "prompt_contract": "route1 v1: one supplied Cited_content passage as D01:S01",
        "source_experiment_tsv": str(args.experiment_tsv),
        "source_experiment_tsv_sha256": sha256(args.experiment_tsv),
        "split_csv": str(args.split_csv),
        "split_csv_sha256": sha256(args.split_csv),
        "prompt_reference": str(args.prompt_reference),
        "prompt_reference_sha256": sha256(args.prompt_reference),
        "split": "train",
        "num_records": len(selected),
        "claim_id_min": min(ids),
        "claim_id_max": max(ids),
        "label_distribution": dict(Counter(split_rows[i]["project_label"] for i in ids)),
        "excluded_conflict_included": False,
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "note": "Generated directly from experiment_dataset.tsv with the same prompt/evidence contract as the frozen Dev M0 prompts; labels stay in the split CSV and are not embedded in model inputs.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
