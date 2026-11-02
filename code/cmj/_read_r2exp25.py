# -*- coding: utf-8 -*-
import json

with open(r"C:\Users\Administrator\AppData\Local\Temp\r2exp25_20261022\annotation_units.jsonl", "r", encoding="utf-8") as f:
    units = [json.loads(l) for l in f if l.strip()]

print(f"共 {len(units)} 条")
for u in units:
    sid = u.get("sample_id", "")
    ct = u.get("citing_title", "")[:40]
    cited = u.get("cited_title", "")[:40]
    marker = u.get("target_marker_text", "")
    ctx = u.get("citing_context", "")[:100]
    print(f"{sid} | {ct} -> {cited} | marker={marker}")
    print(f"  ctx: {ctx}")
    print()
