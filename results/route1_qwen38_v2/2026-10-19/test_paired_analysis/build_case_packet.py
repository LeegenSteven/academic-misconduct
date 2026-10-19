"""Extract a fixed, diverse 20-case review packet from frozen Test data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SELECTIONS = {
    "sciciteval": ["124", "608", "19", "34", "797", "33", "73", "14", "605", "15"],
    "sarol": ["402", "115", "61", "2", "5", "51", "16", "153", "31", "1"],
}
MODELS = ("M0", "Mbio", "Mscv")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def gold_evidence_hit(gold: dict, candidates: list[dict]) -> dict:
    annotated = gold.get("gold_evidence")
    if not annotated:
        return {"status": "not_applicable_given_passage", "matched_candidate_ids": []}
    pairs = {
        (str(doc_id), str(sentence))
        for doc_id, groups in annotated.items()
        for group in groups
        for sentence in group.get("sentences", [])
    }
    matched = [
        candidate["evidence_id"] for candidate in candidates
        if (str(candidate.get("doc_id")), str(candidate.get("sentence_id"))) in pairs
    ]
    return {"status": "annotated_evidence_in_candidates" if matched else "annotated_evidence_not_in_candidates",
            "matched_candidate_ids": matched}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--paired-rows", type=Path, required=True)
    parser.add_argument("--triage-notes", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    repo, run, out = (x.resolve() for x in (args.repo_root, args.run_root, args.out_dir))
    paired = {(row["dataset"], row["claim_id"]): row for row in read_jsonl(args.paired_rows)}
    triage_notes = json.loads(args.triage_notes.read_text(encoding="utf-8"))
    packet = []
    for dataset, ids in SELECTIONS.items():
        data_dir = repo / "results/route1_qwen38_v2/2026-10-15" / dataset
        inputs = {str(row["claim_id"]): row for row in read_jsonl(data_dir / "test.inputs.jsonl")}
        gold = {str(row["claim_id"]): row for row in read_jsonl(data_dir / "test.gold.jsonl")}
        raw = {
            model: {str(row["claim_id"]): row for row in read_jsonl(run / "test" / dataset / model / f"{model}_test_predictions.jsonl")}
            for model in MODELS
        }
        for claim_id in ids:
            row = paired[(dataset, claim_id)]
            source = inputs[claim_id]
            reference = gold[claim_id]
            candidate_evidence = source["candidate_evidence"]
            pattern = "".join("1" if row["correct"][model] else "0" for model in MODELS)
            packet.append({
                "case_id": f"{dataset}:test:{claim_id}",
                "dataset": dataset,
                "claim_id": claim_id,
                "gold": row["gold"],
                "predictions": row["predictions"],
                "correctness_pattern_M0_Mbio_Mscv": pattern,
                "selection_basis": "覆盖模型配对差异、三类边界和无效输出；非随机抽样，不用于估计总体错误率",
                "input_sha256": source.get("input_sha256"),
                "user_prompt": source["user_prompt"],
                "candidate_evidence": candidate_evidence,
                "annotated_gold_evidence": reference.get("gold_evidence"),
                "annotated_evidence_coverage": gold_evidence_hit(reference, candidate_evidence),
                "codex_source_triage": triage_notes[f"{dataset}:test:{claim_id}"],
                "raw_predictions": {model: raw[model][claim_id] for model in MODELS},
                "review": {
                    "source_boundary_review": "pending",
                    "reviewer_ly_label": None,
                    "reviewer_ly_evidence_note": None,
                    "reviewer_cmj_label": None,
                    "reviewer_cmj_evidence_note": None,
                    "adjudication": "pending",
                    "error_cause": "pending",
                },
            })
    if len(packet) != 20 or len({row["case_id"] for row in packet}) != 20:
        raise ValueError("case selection must contain exactly 20 unique cases")
    if {d: sum(row["dataset"] == d for row in packet) for d in SELECTIONS} != {"sciciteval": 10, "sarol": 10}:
        raise ValueError("each Test must contribute exactly ten cases")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "case_review_packet.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in packet:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    for row in packet:
        print(row["case_id"], row["gold"], row["correctness_pattern_M0_Mbio_Mscv"],
              row["annotated_evidence_coverage"]["status"])


if __name__ == "__main__":
    main()
