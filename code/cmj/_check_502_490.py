"""读取502和490的完整候选证据，核对证据ID"""
import json, re

PAYLOAD = r"C:\Users\Administrator\AppData\Local\Temp\ly_45cases_20261020\45条全量初审_20261020\miss45_payload.jsonl"

for cid in ["502", "490"]:
    with open(PAYLOAD, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if str(rec.get("claim_id", "")) == cid:
                inp = rec.get("original_model_input", {})
                if isinstance(inp, str):
                    inp = json.loads(inp)
                up = inp.get("user_prompt", "")
                m = re.search(r"引用论断：(.+?)(?:\n候选证据：|$)", up, re.DOTALL)
                print(f"=== claim {cid} ===")
                print("CLAIM:", m.group(1).strip()[:300] if m else "?")
                print()
                cands = inp.get("candidate_evidence", [])
                print(f"候选证据（共{len(cands)}条）:")
                for c in cands:
                    print(f"  {c.get('evidence_id','?')}: {c.get('text','')[:200]}")
                print()
                break
