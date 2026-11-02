"""45条终版v4 -> v5修正：
1. claim 112: ACCURATE -> NOT_ACCURATE（候选为原始株恒河猴研究，未覆盖viral variants限定）
2. claim 120: ACCURATE -> NOT_ACCURATE（目标14不直接支持人类recovery/long-term immunity）
3. claim 233: 维持NOT_ACCURATE，理由按引用范围重写（D04:S03不在候选）
4. claim 242: 维持NOT_ACCURATE，理由精确化（one-quarter vs 27%无现成容差规则）
5. claim 490: 维持NOT_ACCURATE，理由重写为口径选择（严格口径vs弱口径）
"""
import csv

SRC = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v4_20261020.csv"
DST = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v5_20261021.csv"

with open(SRC, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

changes = []

for r in rows:
    cid = r["claim_id"]

    # === claim 112: ACCURATE -> NOT_ACCURATE ===
    if cid == "112":
        old_label = r["chen_label"]
        r["chen_label"] = "NOT_ACCURATE"
        r["chen_reason"] = (
            "改判：claim核心限定是'reduced neutralizing antibody titres against viral variants是否足够保护尚未完全清楚'。"
            "候选全部为恒河猴原始株研究（D01:S01/D02:S01/D03:S01等均明确rhesus macaques），没有任何候选句提到viral variants。"
            "D01:S01和D03:S02支持'保护重要性尚未确定'的弱背景，但不能支持'针对变异株的中和抗体滴度降低是否足够'这一具体限定。"
            "弱主张不自动豁免限定，候选未覆盖viral variants，改判NOT_ACCURATE。"
        )
        r["chen_attribution_basis"] = "候选为原始株恒河猴研究，未覆盖viral variants限定；not fully understood弱背景成立但具体限定未获支持"
        r["chen_reason_codes"] = "CTX"
        r["chen_evidence_ids"] = "D01:S01;D03:S02"
        changes.append(f"claim 112: {old_label} -> NOT_ACCURATE")

    # === claim 120: ACCURATE -> NOT_ACCURATE ===
    if cid == "120":
        old_label = r["chen_label"]
        r["chen_label"] = "NOT_ACCURATE"
        r["chen_reason"] = (
            "改判：claim说'T cell response might be important for recovery and long-term immunity'。"
            "目标14是恒河猴再感染模型，不是人类COVID-19恢复期或长期免疫研究。"
            "D01:S01说抗体接近/低于阈值时cellular immune responses对rapid virologic control可能重要，可算recovery的间接提示；"
            "D04:S02说CD8+ T细胞在NAb下降时可能贡献保护，更接近'抗体下降时的保护'，不等于'长期免疫'。"
            "候选没有直接支持long-term immunity的句子。两个might降低门槛，但不自动豁免recovery和long-term immunity两个限定，"
            "且目标14为恒河猴模型不能直接等同于人类恢复/长期免疫。改判NOT_ACCURATE。"
        )
        r["chen_attribution_basis"] = "目标14为恒河猴再感染模型，不直接支持人类recovery和long-term immunity；弱措辞不自动豁免限定"
        r["chen_reason_codes"] = "CTX"
        r["chen_evidence_ids"] = "D01:S01;D04:S02"
        changes.append(f"claim 120: {old_label} -> NOT_ACCURATE")

    # === claim 233: 维持NOT_ACCURATE，理由按引用范围重写 ===
    if cid == "233":
        r["chen_reason"] = (
            "按引用范围判断：目标20承担的是'美国居家令期间心理健康挑战增加'从句；"
            "句末'were associated with weight gain in this study'是施引作者自身结果，不由目标20承担。"
            "候选支持居家令期间心理健康下降（D02:S01/D04:S01/D09:S01），但原候选未包含美国亚组一致性证据——"
            "D04:S03（美国亚组与全样本无差异）不在本条候选内（本条候选为D01:S01-D09:S01含D06:S02，无D04:S03）。"
            "D06:S02明确'across the globe'，为多国样本。因此'in the U.S.'限定在原候选范围内未获支持，维持NOT_ACCURATE。"
            "若允许回全文补证D04:S03，则需另议；当前按原候选判断。"
        )
        r["chen_attribution_basis"] = "目标20只承担美国心理健康从句；D04:S03未进入原候选；原候选为多国样本无美国限定支持"
        r["chen_reason_codes"] = "CTX"
        changes.append("claim 233: 维持NOT_ACCURATE，理由按引用范围重写")

    # === claim 242: 维持NOT_ACCURATE，理由精确化 ===
    if cid == "242":
        r["chen_reason"] = (
            "claim的'This increase'由although让步从句可知指健康饮食改善，非体重增加。"
            "肥胖组健康饮食改善更大有全文支持，但该句未进入原候选；原候选D01:S01/D02:S01仅支持体重增加率（27.3%/27.5%），"
            "不能用于支持健康饮食改善在肥胖者中更明显。"
            "此外'one-quarter of the sample reported weight gain'与候选27.3%/27.5%差约2.3-2.5个百分点，"
            "是否接受'约四分之一'作为近似，双方无现成容差规则，不单方增设容差。维持NOT_ACCURATE。"
        )
        r["chen_attribution_basis"] = "This increase指健康饮食改善非体重增加；肥胖组改善有全文支持但不在候选；one-quarter vs 27%无现成容差规则"
        r["chen_reason_codes"] = "CTX;UNK"
        changes.append("claim 242: 维持NOT_ACCURATE，理由精确化")

    # === claim 490: 维持NOT_ACCURATE，理由重写为口径选择 ===
    if cid == "490":
        r["chen_reason"] = (
            "目标14承担第二句'It has been investigated in numerous experiments both in vitro and in vivo'，"
            "不承担首句'IFN-I对MERS-CoV和SARS-CoV有活性'（首句引other_cit）。不能因目标14没覆盖SARS就否定第二句，"
            "也不额外要求单药或结果全部阳性。"
            "候选in vitro有支持：D01:S02（IFNb被评估）、D07:S01（IFNb有体外活性）；"
            "in vivo有支持：D03:S01/D04:S01（RDV vs LPV/RTV-IFNb体内比较，但二者为重复句不计两项）、D04:S02（MIRACLE试验）。"
            "'numerous'是否足够取决于口径：若按'至少体外和体内各一项以上研究'的弱口径，候选可算覆盖；"
            "若按'numerous=多个独立研究'的严格口径，独立in vivo研究仅1-2项，重复句不计，数量范围不足。"
            "当前按严格口径维持NOT_ACCURATE。此为双方口径选择，非事实错误；若共同裁决采用弱口径则可改ACCURATE。"
        )
        r["chen_attribution_basis"] = "目标14承担体内外实验句，不要求覆盖SARS或单药/全部阳性；numerous按严格口径数量不足，重复句不计两项；口径差异待共同裁决"
        r["chen_reason_codes"] = "UNK"
        r["chen_evidence_ids"] = "D01:S02;D07:S01;D03:S01;D04:S02"
        changes.append("claim 490: 维持NOT_ACCURATE，理由重写为口径选择")

# 写入v5
with open(DST, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("=== v5修正记录 ===")
for c in changes:
    print("  " + c)

from collections import Counter
labels = Counter(r["chen_label"] for r in rows)
print(f"\n分布: {dict(labels)}")
print(f"总行数: {len(rows)}")
print(f"v5已写入: {DST}")
