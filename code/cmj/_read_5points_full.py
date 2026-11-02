# -*- coding: utf-8 -*-
"""读取5点全部详细内容"""
import json

F = r"C:\Users\Administrator\AppData\Local\Temp\ly_5points_20261022\02_离线补充诊断\5点人工复核材料_未填写.jsonl"

with open(F, "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f]

for rec in records:
    print(f"=== 点{rec['batch_order']}: {rec['case_id']} ===")
    print(f"施引: {rec['citing_pdf'].get('pmcid','?')} | 被引: {rec['cited_pdf'].get('pmcid','?')}")
    print(f"被引标题: {rec['cited_pdf'].get('title','?')[:80]}")
    print(f"模型标签: {rec['model_label']}")
    print(f"原严格: {rec['original_strict_status']} | 补充: {rec['supplemental_status']}")
    print(f"scope(claim): {rec['scope']}")
    print(f"模型解释: {rec['model_reason_not_accepted'][:300]}")
    print(f"模型选证据: {rec['model_selected_evidence_ids']}")
    print()
    print("候选证据:")
    for c in rec["candidates"]:
        text = c.get("text", c.get("candidate_text", ""))[:120]
        print(f"  {c['evidence_id']}(rank{c.get('retrieval_rank','?')} score{c.get('retrieval_score','?'):.1f}): {text}")
    print()
    print("-" * 70)
    print()
