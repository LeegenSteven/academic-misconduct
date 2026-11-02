# -*- coding: utf-8 -*-
"""重新生成v7裁决报告（含12条理由收紧）"""
import csv

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"
OUT = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\45条三方对比与分歧裁决_陈明进_v7_20261022.md"

with open(V7, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

na = [r for r in rows if r["chen_label"] == "NOT_ACCURATE"]
acc = [r for r in rows if r["chen_label"] == "ACCURATE"]
pending = [r for r in rows if "【待核】" in r["chen_reason"] or "【暂缓】" in r["chen_reason"]]
pending_ids = set(r["claim_id"] for r in pending)
tightened_12 = {"0", "15", "20", "24", "28", "44", "63", "94", "217", "243", "469", "480"}

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
lines.append("### 一、李云v6接收核对指出的2个问题修正")
lines.append("")
lines.append("| claim | 变更内容 |")
lines.append("|---|---|")
lines.append("| 502 | 修正跨案例串号：v6理由误写D03:S01/D04:S01（实为490候选），按502原候选（D01/D02/D08，全为IFN-I和方法学）重写；全文RDV小鼠结果另列注明模型未见 |")
lines.append("| 490 | 补实验计数依据：in vitro 2项（D01:S02含IFNb体外评估、D07:S01 RDV+IFNb体外比较），in vivo 2项（D03/D04逐字重复计1项、D04:S02 MIRACLE试验）；D03与D04去重依据为文本完全一致；加入待共同确认清单（'It'指代IFN-I单药还是泛抗病毒治疗待裁决） |")
lines.append("| 112 | evidence_ids补全：理由中引用了D02:S01/D03:S01说明恒河猴研究，字段同步补全 |")
lines.append("")
lines.append("### 二、12条新暂缓项理由收紧（全部维持NOT_ACCURATE）")
lines.append("")
lines.append("| claim | 收紧方向 |")
lines.append("|---|---|")
lines.append("| 0 | 候选支持TMAO通路但FMO3特异证据缺失；FMO3可能由引用组其他文献承担 |")
lines.append("| 15 | 候选支持MS4A区域但未精确对应MS4A6A/MS4A4E具体基因名；具体成员可能由引用组其他文献承担 |")
lines.append("| 20 | 位点列表有支持，'within past 3 years'时间限定候选未覆盖；多研究引用组不能要求单篇给时间戳 |")
lines.append("| 24 | 部分位点有显著P值及重复分析，但未逐项证明每个基因都满足多数据集校正后显著 |")
lines.append("| 28 | 九项位点数量不矛盾；五篇研究的合并总结不能由当前候选单篇充分覆盖 |")
lines.append("| 44 | 候选未直接列65个SNP；77个transcripts为不同口径不能作数值对照 |")
lines.append("| 63 | 候选为单篇commentary，不能证明'大多数文献为综述'的文献分布论断 |")
lines.append("| 94 | 候选记录阴性结果本身，但施引作者'敲低不足/表达不足'的解释未被直接支持 |")
lines.append("| 217 | 候选支持饮食有变化，但'small'幅度无直接证据；全文REAP-s变化0.81未进原候选 |")
lines.append("| 243 | 候选为单篇全球调查招募国家，不能证明领域文献分布；招募地点≠研究篇数分布 |")
lines.append("| 469 | 候选支持set-enrichment方法存在，但具体算法实现细节候选未完整覆盖 |")
lines.append("| 480 | 原候选仅含比较研究标题，未给出RDV优于组合的具体结果；全文有结果但未进原候选 |")
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
    if r["claim_id"] not in pending_ids:
        reason = r["chen_reason"][:80].replace("\n", " ")
        marker = " *" if r["claim_id"] in tightened_12 else ""
        lines.append(f"| {r['claim_id']}{marker} | {r['chen_reason_codes']} | {reason} |")
lines.append("")
lines.append("\\* v7理由收紧条目")
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

print(f"v7报告已更新: {OUT}")
print(f"行数: {len(lines)}")
