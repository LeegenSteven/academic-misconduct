# -*- coding: utf-8 -*-
"""检查112的完整候选"""
import json

PAYLOAD = r"C:\Users\Administrator\AppData\Local\Temp\ly_45cases_20261020\45条全量初审_20261020\miss45_payload.jsonl"

with open(PAYLOAD, "r", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        if str(rec.get("claim_id", "")) == "112":
            inp = rec.get("original_model_input", {})
            if isinstance(inp, str):
                inp = json.loads(inp)
            cands = inp.get("candidate_evidence", [])
            print(f"112候选证据（共{len(cands)}条）:")
            for c in cands:
                print(f"  {c['evidence_id']}: {c['text'][:120]}")
            break
