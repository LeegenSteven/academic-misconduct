# -*- coding: utf-8 -*-
"""读取5点人工复核材料，提取每点的claim、候选、模型标签和解释"""
import json

F = r"C:\Users\Administrator\AppData\Local\Temp\ly_5points_20261022\02_离线补充诊断\5点人工复核材料_未填写.jsonl"

with open(F, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        rec = json.loads(line)
        print(f"=== 点 {i+1}: {rec.get('case_id','?')} ===")
        print(f"原清单次序: {rec.get('original_list_order','?')}")
        print(f"引用主题: {rec.get('topic','?')}")
        print(f"模型标签: {rec.get('model_label','?')}")
        print(f"claim: {rec.get('claim_text','?')[:300]}")
        print()
        # 候选证据
        cands = rec.get("candidate_evidence", [])
        print(f"候选证据({len(cands)}条):")
        for c in cands[:5]:
            print(f"  {c.get('evidence_id','?')}: {c.get('text','')[:150]}")
        if len(cands) > 5:
            print(f"  ...共{len(cands)}条")
        print()
        # 模型解释
        expl = rec.get("model_explanation", "") or rec.get("explainer_text", "")
        if expl:
            print(f"模型解释: {expl[:400]}")
        print()
        print("-" * 60)
        print()
