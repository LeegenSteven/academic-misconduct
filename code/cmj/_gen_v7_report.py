# -*- coding: utf-8 -*-
"""生成v7裁决报告md"""
import csv

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"
OUT = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\45条三方对比与分歧裁决_陈明进_v7_20261022.md"

with open(V7, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

na = [r for r in rows if r["chen_label"] == "NOT_ACCURATE"]
acc = [r for r in rows if r["chen_label"] == "ACCURATE"]
pending = [r for r in rows if "【待核】" in r["chen_reason"] or "【暂缓】" in r["chen_reason"]]

lines = []
lines.append("# 45条Mbio退化案例三方复核 v7（陈明进个人意见，待共同裁决）")
lines.append("")
lines.append("**版本**：v7（2026-10-22）")
lines.append("**分布**：41 NOT_ACCURATE / 4 ACCURATE")
lines.append("**待核/暂缓**：4条（235、466、490、580）")
lines.append("**冻结gold和Test成绩未修改**")
lines.append("")
lines.append("## v7相对v6的变更")
lines.append("")
lines.append("| claim | 变更内容 |")
lines.append("|---|---|")
lines.append("| 502 | 修正跨案例串号：v6理由误写D03:S01/D04:S01（实为490候选），按502原候选（D01/D02/D08）重写；全文补证另列并注明模型未见 |")
lines.append("| 490 | 补实验计数依据：in vitro 2项（D01:S02、D07:S01）+ in vivo 2项（D03/D04重复句计1项、D04:S02 MIRACLE试验），D03与D04逐字重复去重；加入待共同确认清单（'It'指代IFN-I单药还是泛抗病毒治疗待裁决） |")
lines.append("")
lines.append("## 4条ACCURATE")
lines.append("")
for r in acc:
    lines.append(f"### claim {r['claim_id']}")
    lines.append(f"- **原论断**：{r['claim_text'][:150]}")
    lines.append(f"- **证据**：{r['chen_evidence_ids']}")
    lines.append(f"- **理由**：{r['chen_reason'][:300]}")
    lines.append("")

lines.append("## 4条待核/暂缓")
lines.append("")
for r in pending:
    lines.append(f"### claim {r['claim_id']}（{r['chen_label']}）")
    lines.append(f"- **原论断**：{r['claim_text'][:150]}")
    lines.append(f"- **证据**：{r['chen_evidence_ids']}")
    lines.append(f"- **理由**：{r['chen_reason'][:400]}")
    lines.append("")

lines.append("## 其余37条NOT_ACCURATE")
lines.append("")
lines.append("| claim | 原因码 | 核心理由 |")
lines.append("|---|---|---|")
for r in na:
    if r["claim_id"] not in [p["claim_id"] for p in pending]:
        reason = r["chen_reason"][:80].replace("\n", " ")
        lines.append(f"| {r['claim_id']} | {r['chen_reason_codes']} | {reason} |")
lines.append("")
lines.append("## 待共同裁决事项")
lines.append("")
lines.append("1. **490实验计数与指代**：4项实验计数已补依据，但claim中'It'指代IFN-I单药还是泛抗MERS-CoV治疗需共同确认；若限定IFN-I单药，D03/D04（RDV）和D04:S02（组合疗法）是否计入需裁决。")
lines.append("2. **235地理描述**：Flanagan 27.5%有支持，22%属other_cit；'In the United States'与多国样本是否构成重要歪曲待裁决（与250统一口径）。")
lines.append("3. **466 claim截断**：冻结claim末尾'postmo'被截断，原XML目标更接近repair/immune通路比较；仅就冻结截断文本判NOT_ACCURATE，不诊断真实引用。")
lines.append("4. **580引用范围**：目标只承担diet从句，不要求mental health；'in children'省略obesity限定是否构成重要歪曲待裁决。")
lines.append("5. **250地理描述分歧**：多国研究vs conducted in US，继续保留。")
lines.append("")
lines.append("---")
lines.append("*本文件为陈明进个人复核意见，非双方共同裁决结果。冻结gold、模型输入和正式Test成绩均未修改。*")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"v7报告已生成: {OUT}")
print(f"行数: {len(lines)}")
