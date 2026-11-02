"""45条终版v3 -> v4修正：
1. claim 20 归因列旧文字更新
2. claim 490 区分IFN单药/联合方案/numerous限定
3. claim 502 明确承接remdesivir，与候选IFN区分
4. 扫描全部行归因列与reason一致性
"""
import csv, os, shutil

SRC = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进终版v3_20261020.csv"
DST = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进终版v4_20261020.csv"

with open(SRC, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

changes = []

for r in rows:
    cid = r["claim_id"]

    # === claim 20: 归因列旧文字更新 ===
    if cid == "20":
        old_attr = r["chen_attribution_basis"]
        r["chen_attribution_basis"] = "claim含within the past 3 years时间限定，候选未明确支持该时间范围；位点列表虽被支持，但多研究概括的时间限定未完整获证"
        r["chen_reason"] = "候选D01提及Hollingsworth et al.，D07提及three other consortia，并非纯单篇Naj；但claim含within the past 3 years时间限定，候选未明确支持该时间范围；且位点列表虽被支持，多研究概括的时间限定未完整获证。"
        changes.append(f"claim 20: 归因列从'{old_attr[:30]}...'更新为时间限定缺失")

    # === claim 490: 区分IFN单药/联合方案/numerous限定 ===
    if cid == "490":
        old_reason = r["chen_reason"]
        old_attr = r["chen_attribution_basis"]
        r["chen_reason"] = (
            "目标引用承担IFN-I已在numerous experiments both in vitro and in vivo中被研究。"
            "候选需区分三类：(1)IFN单药仅in vitro有支持——D01:S02说IFNb在in vitro被评估，"
            "D07:S01说IFNb有in vitro抗病毒活性；(2)联合方案LPV/RTV-IFNb有in vivo比较——"
            "D03:S01/D04:S01说RDV在in vitro和in vivo优于LPV/RTV-IFNb，但这是RDV vs 联合方案，"
            "非IFN单药in vivo；D04:S02说interferon treatment不改善临床结局，MIRACLE trial评估联合方案；"
            "(3)numerous限定不成立——候选仅2-3个体外研究，无IFN单药in vivo实验，数量不足以支持numerous。"
            "此外候选无SARS-CoV的IFN活性证据。"
        )
        r["chen_attribution_basis"] = (
            "IFN单药仅in vitro有支持(D01:S02/D07:S01)；D03:D04的in vivo是RDV vs LPV/RTV-IFNb联合方案比较，"
            "非IFN单药；numerous experiments限定候选数量不足；无SARS-CoV证据"
        )
        changes.append(f"claim 490: reason/归因区分IFN单药、联合方案、numerous限定")

    # === claim 502: 明确承接remdesivir ===
    if cid == "502":
        old_reason = r["chen_reason"]
        old_attr = r["chen_attribution_basis"]
        r["chen_reason"] = (
            "claim的The antiviral efficacy承接前文remdesivir(RDV)，说RDV的抗病毒疗效在MERS-CoV小鼠和恒河猴模型中进一步确认。"
            "候选D01:S01明确支持的是type I interferon在体内的抗病毒效果——IFN alpha皮下注射(恒河猴)和IFNb鼻内给药(腺病毒hDPP4小鼠模型)。"
            "药物指代不同：claim指RDV，候选支持IFN-I，因此候选不支持claim中RDV在两种模型中的疗效。"
            "候选中无RDV在mouse和rhesus macaque模型中疗效的直接证据。"
        )
        r["chen_attribution_basis"] = (
            "claim承接remdesivir(RDV)，候选D01:S01仅支持type I interferon的体内疗效，药物指代不同(RDV vs IFN-I)"
        )
        r["chen_evidence_ids"] = "D01:S01"
        changes.append(f"claim 502: reason/归因明确RDV与候选IFN的指代区别")

# 扫描全部行：归因列与reason一致性检查
print("=== 归因列与reason一致性扫描 ===")
for r in rows:
    cid = r["claim_id"]
    label = r["chen_label"]
    reason = r["chen_reason"]
    attr = r["chen_attribution_basis"]
    # 检查归因列是否为空或明显与label不匹配
    if not attr.strip():
        print(f"  claim {cid} ({label}): 归因列为空")
    # 检查归因列是否包含旧版关键词
    if "单篇Naj" in attr and cid != "20":
        print(f"  claim {cid}: 归因列含'单篇Naj'旧文字")
    if "D04:S03" in attr and cid == "233":
        print(f"  claim 233: 归因列仍含D04:S03")

print()
print("=== 修正记录 ===")
for c in changes:
    print("  " + c)

# 写入v4
with open(DST, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print()
print(f"v4已写入: {DST}")
print(f"总行数: {len(rows)}")

# 统计分布
from collections import Counter
labels = Counter(r["chen_label"] for r in rows)
print(f"标签分布: {dict(labels)}")
