#!/usr/bin/env python3
"""Rebuild all three SciCiteVal inputs without exposing source row IDs.

Only the input version changes. The provisional v1 split and quarantined
annotations are preserved. No labels are inferred or repaired by this script.
Run from the repository root; all dependencies are in the standard library.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE_REVISION = "88bf515d33dc484185174443a66f6dbf536850af"
EXPECTED_SOURCE_SHA256 = "01e9ab2337cafb3fa1c590311cd082a7628a3e239fbcd0ad2757a0e9aaa71b40"
EXPECTED_SPLIT_WINDOWS_SHA256 = "1645eef964f8e6f223582519c36553d59344216fdc1e108b0de2a607df0bc150"
EXPECTED_COUNTS = {"train": 713, "dev": 54, "test": 257, "excluded_conflict": 10}
EXPECTED_CONFLICT_IDS = {358, 359, 528, 529, 556, 557, 562, 563, 590, 591}
LABELS = {"Correct": "ACCURATE", "Incorrect": "NOT_ACCURATE", "Unrelated": "IRRELEVANT"}
V1 = Path("results/route1_qwen38_v1/2026-10-13")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> dict:
    raw = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")
    path.write_bytes(raw)
    return {"path": path.name, "records": len(rows), "bytes": len(raw), "sha256": sha256(raw)}


def prompt_sha256(system_prompt: str, user_prompt: str) -> str:
    payload = {"system_prompt": system_prompt, "user_prompt": user_prompt}
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def make_record(row_id: int, source: dict[str, str], system_prompt: str) -> dict:
    # External claim_id is for joining predictions to gold. Model callers must
    # pass ONLY system_prompt and user_prompt as the two chat messages.
    context, cited = source["Citation_context"], source["Cited_content"]
    user_prompt = f"施引上下文：{context}\n被引内容：\nD01:S01 | {cited}\n请只输出符合要求的 JSON。"
    return {
        "claim_id": row_id,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "allowed_evidence_ids": ["D01:S01"],
        "candidate_evidence": [{"evidence_id": "D01:S01", "text": cited, "locator": "cited_content"}],
        "input_warning": "SciCiteVal replay input; D01:S01 is the supplied Cited_content passage.",
        "input_sha256": prompt_sha256(system_prompt, user_prompt),
    }


def group_overlap(split_rows: list[dict], key_fn) -> dict:
    owners: dict[str, set[str]] = defaultdict(set)
    for row in split_rows:
        if row["split"] in {"train", "dev", "test"}:
            key = key_fn(row)
            if key:
                owners[key].add(row["split"])
    return {key: sorted(value) for key, value in owners.items() if len(value) > 1}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-tsv", type=Path, default=Path("inputs/demo30/scicite_original.tsv"))
    parser.add_argument("--split-csv", type=Path, default=V1 / "sciciteval_group_split_provisional_2026-10-13.csv")
    parser.add_argument("--prompt-reference", type=Path, default=V1 / "sciciteval_dev_m0_prompts_2026-10-13.jsonl")
    parser.add_argument("--dev-gold-reference", type=Path, default=V1 / "sciciteval_dev_gold_2026-10-13.jsonl")
    parser.add_argument("--conflict-audit", type=Path, default=V1 / "sciciteval_conflict_source_audit_2026-10-13.csv")
    parser.add_argument("--output-dir", type=Path, default=Path("results/route1_qwen38_v2/2026-10-15/sciciteval"))
    args = parser.parse_args()

    source_bytes, split_bytes = args.experiment_tsv.read_bytes(), args.split_csv.read_bytes()
    if sha256(source_bytes) != EXPECTED_SOURCE_SHA256:
        raise ValueError("Source TSV differs from frozen v1; do not silently substitute a new source")
    split_lf = split_bytes.replace(b"\r\n", b"\n")
    if sha256(split_lf.replace(b"\n", b"\r\n")) != EXPECTED_SPLIT_WINDOWS_SHA256:
        raise ValueError("Split content differs from frozen v1 (LF/CRLF changes alone are allowed)")
    with args.experiment_tsv.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle, delimiter="\t"))
    with args.split_csv.open(encoding="utf-8-sig", newline="") as handle:
        split_rows = list(csv.DictReader(handle))
    if len(source_rows) != 1034 or len(split_rows) != 1034:
        raise ValueError("Expected all 1,034 original source/split records")
    mapping = {int(row["row_id"]): row for row in split_rows}
    if len(mapping) != 1034 or set(mapping) != set(range(1034)):
        raise ValueError("Duplicate or missing source row ID")
    counts = dict(Counter(row["split"] for row in split_rows))
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"Frozen split counts changed: {counts}")
    excluded = {row_id for row_id, row in mapping.items() if row["split"] == "excluded_conflict"}
    if excluded != EXPECTED_CONFLICT_IDS:
        raise ValueError("Quarantined conflict membership changed")
    for row_id, source in enumerate(source_rows):
        meta = mapping[row_id]
        if meta["source_label"] != source["Label"] or meta["project_label"] != LABELS[source["Label"]]:
            raise ValueError(f"Source/split label mismatch at {row_id}")
        if not source["Citation_context"].strip() or not source["Cited_content"].strip():
            raise ValueError(f"Empty source text at {row_id}")

    references = read_jsonl(args.prompt_reference)
    if len(references) != 54 or len({row["system_prompt"] for row in references}) != 1:
        raise ValueError("Expected one frozen system prompt across all 54 Dev records")
    system_prompt = references[0]["system_prompt"]
    dev_ids = [row_id for row_id in range(1034) if mapping[row_id]["split"] == "dev"]
    if [int(row["claim_id"]) for row in references] != dev_ids:
        raise ValueError("Frozen Dev prompt ID/order mismatch")
    old_dev_gold = read_jsonl(args.dev_gold_reference)
    if [(int(row["sample_id"]), row["project_label"]) for row in old_dev_gold] != [(row_id, mapping[row_id]["project_label"]) for row_id in dev_ids]:
        raise ValueError("Frozen Dev gold ID/order/label mismatch")
    # Establish that the only model-visible change to frozen Dev is removing
    # the source identifier, without changing any evidence or passage text.
    for old in references:
        row_id = int(old["claim_id"])
        fresh = make_record(row_id, source_rows[row_id], system_prompt)
        if old["user_prompt"] != f"claim_id: {row_id}\n" + fresh["user_prompt"]:
            raise ValueError(f"Unexpected Dev prompt difference at {row_id}")
        if old["allowed_evidence_ids"] != fresh["allowed_evidence_ids"]:
            raise ValueError(f"Unexpected Dev evidence ID difference at {row_id}")

    overlaps = {
        "group_key": group_overlap(split_rows, lambda row: row["group_key"]),
        "source_paper_id": group_overlap(split_rows, lambda row: row["source_paper_id"]),
        "citation_context_exact": group_overlap(split_rows, lambda row: source_rows[int(row["row_id"])]["Citation_context"]),
        "cited_content_exact": group_overlap(split_rows, lambda row: source_rows[int(row["row_id"])]["Cited_content"]),
    }
    if any(overlaps.values()):
        raise ValueError("A frozen grouping or exact text occurs across splits; review before proceeding")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    files, label_counts, id_digests = {}, {}, {}
    for split in ("train", "dev", "test"):
        ids = [row_id for row_id in range(1034) if mapping[row_id]["split"] == split]
        inputs = [make_record(row_id, source_rows[row_id], system_prompt) for row_id in ids]
        gold = [{"claim_id": row_id, "label": mapping[row_id]["project_label"]} for row_id in ids]
        if any(re.search(r"(?m)^claim_id\s*:", row["user_prompt"]) for row in inputs):
            raise ValueError("Source ID remains in a model-visible prompt")
        files[f"{split}.inputs"] = write_jsonl(args.output_dir / f"{split}.inputs.jsonl", inputs)
        files[f"{split}.gold"] = write_jsonl(args.output_dir / f"{split}.gold.jsonl", gold)
        label_counts[split] = dict(Counter(row["label"] for row in gold))
        id_digests[split] = sha256(json.dumps(ids, separators=(",", ":")).encode())
    quarantine = [{"row_id": row_id, "frozen_split_metadata": mapping[row_id], "original_record": source_rows[row_id], "status": "unresolved_source_annotation_conflict"} for row_id in sorted(excluded)]
    files["conflicts.quarantine"] = write_jsonl(args.output_dir / "conflicts.quarantine.jsonl", quarantine)
    for name, raw in (("split.frozen_v1.csv", split_bytes), ("conflict_source_audit.frozen_v1.csv", args.conflict_audit.read_bytes())):
        (args.output_dir / name).write_bytes(raw)
        files[name] = {"path": name, "bytes": len(raw), "sha256": sha256(raw)}

    report = {
        "status": "passed_static_validation_no_model_run",
        "source_rows": 1034,
        "split_counts": counts,
        "labels_match_original_source": True,
        "conflict_ids_unchanged": sorted(excluded),
        "source_group_and_exact_text_cross_split_overlap_counts": {key: len(value) for key, value in overlaps.items()},
        "input_gold_ids_order_labels_aligned": True,
        "dev_prompt_change": "Only the leading claim_id line was removed; system and supplied evidence text are unchanged",
        "model_prompt_contains_source_id_field": False,
        "model_input_policy": "Only system_prompt and user_prompt are passed to the model; external claim_id remains for joins",
        "no_test_model_run_or_selection": True,
        "conflicts_resolved": False,
    }
    (args.output_dir / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    manifest = {
        "input_version": "route1_qwen38_inputs_v2_2026-10-15",
        "dataset_split_version": "SciCiteVal_v1_provisional_2026-10-13_unchanged",
        "base_repository_revision": BASE_REVISION,
        "builder": "code/ly/build_sciciteval_inputs_v2.py",
        "builder_sha256": sha256(Path(__file__).read_bytes()),
        "source_files": {
            "experiment_tsv": {"path": "inputs/demo30/scicite_original.tsv", "sha256": sha256(source_bytes)},
            "split_csv": {"path": (V1 / args.split_csv.name).as_posix(), "sha256": sha256(split_bytes), "sha256_lf": sha256(split_lf), "frozen_windows_crlf_sha256": EXPECTED_SPLIT_WINDOWS_SHA256},
            "prompt_reference": {"path": (V1 / args.prompt_reference.name).as_posix(), "sha256": sha256(args.prompt_reference.read_bytes())},
            "dev_gold_reference": {"path": (V1 / args.dev_gold_reference.name).as_posix(), "sha256": sha256(args.dev_gold_reference.read_bytes())},
        },
        "system_prompt_sha256": sha256(system_prompt.encode("utf-8")),
        "input_sha256_definition": "SHA256 of UTF-8 json.dumps({system_prompt,user_prompt}, ensure_ascii=False, sort_keys=True, separators=(',',':'))",
        "source_text_policy": "Original Citation_context and Cited_content preserved exactly; one supplied passage D01:S01",
        "reasoning": "off; must also be explicitly applied and verified by the HF inference/training caller",
        "counts": EXPECTED_COUNTS,
        "label_distribution": label_counts,
        "id_order_sha256": id_digests,
        "files": files,
        "prior_gguf_results": "Historical preruns only; rerun official M0 using these inputs before adapter comparisons",
        "limitations": ["The 10 conflicting annotations remain unresolved and excluded", "Dev IRRELEVANT has only 4 examples from one source group", "Supplied passages are dataset replay evidence, not proof of a real two-PDF citation link"],
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "counts": counts, "output_dir": args.output_dir.as_posix()}, ensure_ascii=True))


if __name__ == "__main__":
    main()
