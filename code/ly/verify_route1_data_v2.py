#!/usr/bin/env python3
"""Independently verify the delivered route-one v2 data; never run a model."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

EXPECTED = {"sciciteval": {"train": 713, "dev": 54, "test": 257}, "sarol": {"train": 2141, "dev": 316, "test": 606}}
LABELS = {"ACCURATE", "NOT_ACCURATE", "IRRELEVANT"}
FORBIDDEN_INPUT_KEYS = {"label", "project_label", "source_label", "gold", "gold_evidence", "evidence_missing", "training_label_ready", "split"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def reject_gold_fields(value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_INPUT_KEYS:
                raise ValueError(f"Gold/split field in input: {key}")
            reject_gold_fields(child)
    elif isinstance(value, list):
        for child in value:
            reject_gold_fields(child)


def verify_pair(inputs: list[dict], gold: list[dict], count: int, dataset: str, system_sha256: str | None = None) -> dict:
    if len(inputs) != count or len(gold) != count:
        raise ValueError(f"Unexpected counts in {dataset}")
    ids = [row["claim_id"] for row in inputs]
    if len(set(ids)) != count or any(type(item) is not int for item in ids):
        raise ValueError("IDs must be unique integers within this dataset/split")
    if ids != [row["claim_id"] for row in gold]:
        raise ValueError("Input/gold ID or order mismatch")
    if any(row["label"] not in LABELS for row in gold):
        raise ValueError("Unknown gold label")
    evidence_counts = Counter()
    for row in inputs:
        reject_gold_fields(row)
        system, user = row["system_prompt"], row["user_prompt"]
        if not isinstance(system, str) or not system.strip() or not isinstance(user, str) or not user.strip():
            raise ValueError("Empty model message")
        for message in (system, user):
            if re.search(r"(?mi)^\s*(claim_id|sample_id|row_id|source_sample_id|split|gold|project_label)\s*:", message):
                raise ValueError("Tracking or annotation field in model prompt")
        if system_sha256 is not None and digest(system.encode("utf-8")) != system_sha256:
            raise ValueError("System prompt differs from frozen dataset prompt")
        if re.search(r"(?mi)^D\d+:S\d+\s*\|\s*doc_id\s*=", user):
            raise ValueError("Real source document ID in model evidence line")
        payload = json.dumps({"system_prompt": system, "user_prompt": user}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if row["input_sha256"] != digest(payload):
            raise ValueError("Per-record model-prompt hash mismatch")
        candidates = row["candidate_evidence"]
        candidate_ids = [candidate["evidence_id"] for candidate in candidates]
        if candidate_ids != row["allowed_evidence_ids"] or len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("Allowed evidence/candidate order or uniqueness mismatch")
        if any(not re.fullmatch(r"D\d{2,}:S\d{2,}", item) for item in candidate_ids):
            raise ValueError("Malformed compact evidence ID")
        for candidate in candidates:
            if not candidate["text"].strip() or f"{candidate['evidence_id']} | {candidate['text']}" not in user:
                raise ValueError("Candidate evidence text missing from model prompt")
        expected_candidates = 1 if dataset == "sciciteval" else 10
        if len(candidates) != expected_candidates:
            raise ValueError("Evidence count differs from frozen input contract")
        evidence_counts[len(candidates)] += 1
    return {"records": count, "unique_ids": count, "input_gold_order_aligned": True, "label_distribution": dict(sorted(Counter(row["label"] for row in gold).items())), "candidate_count_distribution": dict(evidence_counts), "prompt_hashes_match": True, "gold_or_tracking_field_in_model_payload": False}


def check_manifest_files(data_root: Path, repo_root: Path) -> int:
    # Dataset manifests have different legacy layouts. Check both explicitly;
    # paths are resolved relative to the delivery root, never the machine that
    # originally built the files.
    checked = 0
    scv = json.loads((data_root / "sciciteval/manifest.json").read_text(encoding="utf-8"))
    entries = [(data_root / "sciciteval" / value["path"], value) for value in scv["files"].values()]
    sarol = json.loads((data_root / "sarol/manifest.json").read_text(encoding="utf-8"))
    for split in EXPECTED["sarol"]:
        entries += [(data_root / "sarol" / Path(value["path"]).name, value) for value in sarol["splits"][split]["outputs"].values()]
    entries += [(repo_root / value["path"], value) for value in scv["source_files"].values()]
    entries += [(repo_root / value["path"], value) for value in sarol["source_files"]]
    entries += [(repo_root / scv["builder"], {"sha256": scv["builder_sha256"]})]
    entries += [(repo_root / value["path"], value) for value in (sarol["generator"], sarol["v1_manifest"])]
    for dataset in EXPECTED:
        smoke = json.loads((data_root / dataset / "smoke32.manifest.json").read_text(encoding="utf-8"))
        for value in list(smoke["sources"].values()) + list(smoke["outputs"].values()) + [smoke["generator"]]:
            entries.append((repo_root / value["path"], value))
    for path, meta in entries:
        raw = path.read_bytes()
        if ("bytes" in meta and len(raw) != meta["bytes"]) or digest(raw) != meta["sha256"]:
            raise ValueError(f"Manifest file digest/size mismatch: {path.name}")
        checked += 1
    return checked


def verify_delivery_checksums(repo_root: Path) -> None:
    manifest_path = repo_root / "PACKAGE_MANIFEST.json"
    if not manifest_path.exists():
        return  # A repository checkout can use the dataset manifests alone.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for value in manifest["files"]:
        path = (repo_root / value["path"]).resolve()
        if not path.is_relative_to(repo_root.resolve()):
            raise ValueError("Delivery manifest path escapes the package directory")
        raw = path.read_bytes()
        if len(raw) != value["bytes"] or digest(raw) != value["sha256"]:
            raise ValueError(f"Delivery checksum mismatch: {value['path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("results/route1_qwen38_v2/2026-10-15"))
    parser.add_argument("--report", type=Path, help="Optional separate runtime report; no model is loaded")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    verify_delivery_checksums(repo_root)
    result = {"status": "passed_static_validation_no_model_run", "datasets": {}, "manifest_files_checked": check_manifest_files(args.data_root, repo_root), "total_active_records": 0}
    datasets = {}
    for dataset, splits in EXPECTED.items():
        manifest = json.loads((args.data_root / dataset / "manifest.json").read_text(encoding="utf-8"))
        result["datasets"][dataset] = {}
        datasets[dataset] = {}
        for split, count in splits.items():
            folder = args.data_root / dataset
            inputs = read_jsonl(folder / f"{split}.inputs.jsonl")
            gold = read_jsonl(folder / f"{split}.gold.jsonl")
            result["datasets"][dataset][split] = verify_pair(inputs, gold, count, dataset, manifest["system_prompt_sha256"])
            datasets[dataset][split] = (inputs, gold)
            result["total_active_records"] += count
        folder = args.data_root / dataset
        smoke_inputs = read_jsonl(folder / "smoke32.inputs.jsonl")
        smoke_gold = read_jsonl(folder / "smoke32.gold.jsonl")
        smoke_manifest = json.loads((folder / "smoke32.manifest.json").read_text(encoding="utf-8"))
        verify_pair(smoke_inputs, smoke_gold, 32, dataset, manifest["system_prompt_sha256"])
        train_inputs, train_gold = datasets[dataset]["train"]
        positions = smoke_manifest["selected_source_positions_zero_based"]
        if smoke_inputs != [train_inputs[index] for index in positions] or smoke_gold != [train_gold[index] for index in positions]:
            raise ValueError("Smoke records are not an unchanged Train subset")
        if {row["label"] for row in smoke_gold} != LABELS:
            raise ValueError("Smoke must cover all three labels")
        result["datasets"][dataset]["smoke32"] = {"records": 32, "unchanged_train_subset": True, "all_three_labels_covered": True, "not_a_formal_evaluation_split": True}
    scv_dir = args.data_root / "sciciteval"
    with (scv_dir / "split.frozen_v1.csv").open(encoding="utf-8-sig", newline="") as handle:
        split_rows = list(csv.DictReader(handle))
    scv_mapping = {int(row["row_id"]): row for row in split_rows}
    active_ids = set()
    for split in EXPECTED["sciciteval"]:
        inputs, gold = datasets["sciciteval"][split]
        expected_ids = [row_id for row_id in range(1034) if scv_mapping[row_id]["split"] == split]
        if [row["claim_id"] for row in inputs] != expected_ids:
            raise ValueError("SciCiteVal split membership/order changed")
        if any(row["label"] != scv_mapping[row["claim_id"]]["project_label"] for row in gold):
            raise ValueError("SciCiteVal gold changed")
        if active_ids.intersection(expected_ids):
            raise ValueError("SciCiteVal ID occurs in multiple active splits")
        active_ids.update(expected_ids)
    quarantine = read_jsonl(scv_dir / "conflicts.quarantine.jsonl")
    quarantined_ids = {row["row_id"] for row in quarantine}
    if len(quarantine) != 10 or quarantined_ids & active_ids or active_ids | quarantined_ids != set(range(1034)):
        raise ValueError("Conflicts are missing, duplicated or not isolated")
    result["sciciteval_original_1034_rows_fully_accounted_for"] = True
    result["quarantined_conflicts"] = 10
    result["sarol_join_key_policy"] = "(dataset, split, claim_id); claim_id alone is not globally unique"
    result["no_model_inference_training_or_test_selection_performed"] = True
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered)


if __name__ == "__main__":
    main()
