"""Produce two independent review forms without gold or model outputs."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--cases", type=Path, required=True)
parser.add_argument("--out-dir", type=Path, required=True)
args = parser.parse_args()
cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
if len(cases) != 20:
    raise ValueError("expected 20 cases")
args.out_dir.mkdir(parents=True, exist_ok=True)
for reviewer in ("李云", "陈明进"):
    target = args.out_dir / f"盲复核表_{reviewer}_20261019.jsonl"
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            row = {
                "case_id": case["case_id"],
                "dataset": case["dataset"],
                "user_prompt": case["user_prompt"],
                "candidate_evidence": case["candidate_evidence"],
                "reviewer": reviewer,
                "review_date": None,
                "label_judgment": None,
                "evidence_ids": [],
                "evidence_basis": None,
                "reason": None,
                "review_status": "pending_independent_review"
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(target, "records=20", "blinded=true")
