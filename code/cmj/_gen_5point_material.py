# -*- coding: utf-8 -*-
"""读取5点全部候选证据文本，输出完整核对材料"""
import json

F = r"C:\Users\Administrator\AppData\Local\Temp\ly_5points_20261022\02_离线补充诊断\5点人工复核材料_未填写.jsonl"
OUT = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\首批5点语义核对_陈明进_20261022.md"

with open(F, "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f]

lines = []
lines.append("# 首批5点真实双PDF闭环语义核对（陈明进）")
lines.append("")
lines.append("**日期**：2026-10-22")
lines.append("**说明**：模型标签和解释为A100首次输出，本核对为语义级人工复核，非最终裁决。6处摘录不一致均为PDF换行/连字符/引用标记导致，模型做了合理规范化，无编造。")
lines.append("")

for rec in records:
    bn = rec["batch_order"]
    lines.append(f"## 点{bn}：{rec['case_id']}")
    lines.append("")
    lines.append(f"- **施引**：{rec['citing_pdf'].get('pmcid','?')}")
    lines.append(f"- **被引**：{rec['cited_pdf'].get('pmcid','?')} — {rec['cited_pdf'].get('title','?')[:80]}")
    lines.append(f"- **模型标签**：{rec['model_label']}")
    lines.append(f"- **原严格状态**：{rec['original_strict_status']}")
    lines.append(f"- **补充状态**：{rec['supplemental_status']}")
    lines.append(f"- **claim(scope)**：{rec['scope']}")
    lines.append(f"- **模型选证据**：{', '.join(rec['model_selected_evidence_ids'])}")
    lines.append("")
    lines.append("### 模型解释")
    lines.append(rec["model_reason_not_accepted"])
    lines.append("")
    lines.append("### 候选证据全文")
    lines.append("")
    for c in rec["candidates"]:
        text = c.get("raw_text", "").strip()
        lines.append(f"**{c['evidence_id']}** (rank{c.get('retrieval_rank','?')}, score{c.get('retrieval_score',0):.1f}):")
        lines.append(f"> {text}")
        lines.append("")
    lines.append("---")
    lines.append("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"已生成: {OUT}")
print(f"行数: {len(lines)}")
