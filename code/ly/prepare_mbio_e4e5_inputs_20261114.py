"""Prepare frozen Sarol Dev E4/E5 BM25 top-20 model inputs.

This is preparation only. It does not run a model and never reads gold to
build candidates. It uses the frozen Sarol claims/corpus and the existing
build_sarol_inputs_v2 implementation (k1=1.2, b=0.75) to create separate E4
and E5 input/gold JSONL files for A100 inference.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_builder(path: Path):
    spec = importlib.util.spec_from_file_location("sarol_inputs_v2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    source = repo / "data" / "quality_v1" / "sarol"
    builder = load_builder(repo / "code" / "ly" / "build_sarol_inputs_v2.py")
    scope = json.loads(args.scope.read_text(encoding="utf-8"))
    e4_ids = [str(x) for x in scope["e4"]["claim_ids"]]
    e5_ids = [str(x) for x in scope["e5"]["claim_ids"]]
    if len(e4_ids) != 24 or len(e5_ids) != 10 or set(e4_ids) & set(e5_ids):
        raise ValueError("Scope must contain disjoint E4=24 and E5=10 IDs")

    claims = load_jsonl(source / "claims-dev-model.jsonl")
    corpus = load_jsonl(source / "corpus.jsonl")
    corpus_by_id = {int(row["doc_id"]): row for row in corpus}
    if len(corpus_by_id) != len(corpus):
        raise ValueError("Duplicate corpus doc_id")

    by_id: dict[str, tuple[dict, dict]] = {}
    for claim in claims:
        cid = str(claim["id"])
        candidates = builder.build_candidates(claim.get("cited_doc_ids") or [], corpus_by_id)
        ranked = builder.compact_evidence_ids(
            builder.bm25_rank(claim.get("claim", ""), candidates)[:20]
        )
        user = builder.render_user_prompt(claim["claim"], ranked)
        inp = {
            "claim_id": int(claim["id"]),
            "system_prompt": builder.SYSTEM_PROMPT,
            "user_prompt": user,
            "candidate_evidence": ranked,
            "allowed_evidence_ids": [item["evidence_id"] for item in ranked],
            "input_sha256": builder.model_input_sha256(builder.SYSTEM_PROMPT, user),
        }
        gold = {
            "claim_id": int(claim["id"]),
            "label": claim["gold"],
            "gold_evidence": claim.get("evidence", {}),
            "evidence_missing": claim.get("evidence_missing"),
            "source_sample_id": claim.get("sample_id"),
        }
        by_id[cid] = (inp, gold)

    if len(by_id) != 316:
        raise ValueError(f"Expected 316 Dev claims, got {len(by_id)}")

    args.output.mkdir(parents=True, exist_ok=True)
    groups = {"e4": e4_ids, "e5": e5_ids}
    outputs = {}
    for group, ids in groups.items():
        inputs = [by_id[cid][0] for cid in ids]
        gold = [by_id[cid][1] for cid in ids]
        input_path = args.output / f"{group}.inputs.top20.jsonl"
        gold_path = args.output / f"{group}.gold.jsonl"
        write_jsonl(input_path, inputs)
        write_jsonl(gold_path, gold)
        outputs[group] = {
            "records": len(inputs),
            "input": {"path": input_path.name, "bytes": input_path.stat().st_size, "sha256": sha256(input_path)},
            "gold": {"path": gold_path.name, "bytes": gold_path.stat().st_size, "sha256": sha256(gold_path)},
            "claim_ids": ids,
        }

    manifest = {
        "version": "route1_mbio_e4e5_inputs_top20_20261114",
        "status": "prepared_not_run",
        "split": "sarol/dev",
        "retriever": {"name": "Frozen v1 grouped BM25", "top_k": 20, "k1": 1.2, "b": 0.75},
        "source_files": {
            "claims-dev-model.jsonl": sha256(source / "claims-dev-model.jsonl"),
            "corpus.jsonl": sha256(source / "corpus.jsonl"),
            "scope": sha256(args.scope),
            "builder": sha256(repo / "code" / "ly" / "build_sarol_inputs_v2.py"),
        },
        "outputs": outputs,
        "test_anchor_ids": ["29", "156", "601", "61", "253", "504", "385", "426", "604"],
        "constraints": {
            "test_used_for_selection": False,
            "gold_modified": False,
            "joint_or_score_modified": False,
            "model_inference_performed": False,
        },
    }
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
