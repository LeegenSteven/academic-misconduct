# -*- coding: utf-8 -*-
"""修正v7：490去掉确定实验计数保留待核，37条改38条"""
import csv
import shutil

CSV = r"C:\Users\Administrator\Desktop\miss45_review_陈明进v7_20261022.csv"
MD = r"C:\Users\Administrator\Desktop\45条三方对比与分歧裁决_陈明进_v7_20261022.md"

# 备份
shutil.copy(CSV, CSV + ".bak")
shutil.copy(MD, MD + ".bak")

# === 修正CSV中490的理由 ===
new_reason_490 = (
    "【待核】目标14只承担第二句'It has been investigated in numerous experiments both in vitro and in vivo'，"
    "不承担首句'IFN-I对MERS-CoV/SARS-CoV有活性'（首句引other_cit），也不要求单药或结果全部阳性。"
    "原候选中有in vitro相关提及（D01:S02含IFNb体外抗MERS-CoV活性评估、D07:S01含RDV与IFNb体外抗病毒活性比较）"
    "和in vivo相关提及（D03:S01/D04:S01为重复概述句、D04:S02为MIRACLE试验），"
    "但现有概述句、结果句及试验目的句不足以直接合计为确定数量的独立实验；"
    "D03:S01与D04:S01文本完全一致，为重复句不能计作两项独立研究。"
    "'numerous experiments'是否被原候选充分支持需共同确认，本轮不预设确定计数。"
    "待确认点：claim中'It'指代IFN-I单药还是泛抗MERS-CoV治疗；"
    "若限定IFN-I单药，则D03/D04（RDV相关）和D04:S02（组合疗法）是否计入需共同裁决。"
    "不要求多个独立论文，也不要求单药或全部阳性。"
)

rows = []
with open(CSV, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        if row.get("claim_id", "") == "490":
            row["chen_reason"] = new_reason_490
        rows.append(row)

with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("CSV 490理由已修正")

# === 修正md ===
with open(MD, "r", encoding="utf-8") as f:
    content = f.read()

# 1. v7变更表中490描述
old_v7_change = (
    "| 490 | 补实验计数依据：in vitro 2项（D01:S02含IFNb体外评估、D07:S01 RDV+IFNb体外比较），"
    "in vivo 2项（D03/D04逐字重复计1项、D04:S02 MIRACLE试验）；"
    "D03与D04去重依据为文本完全一致；加入待共同确认清单（'It'指代IFN-I单药还是泛抗病毒治疗待裁决） |"
)
new_v7_change = (
    "| 490 | 去掉确定实验计数，保留待核：原候选有in vitro和in vivo相关提及，"
    "但概述句、结果句及MIRACLE试验目的句不足以直接合计为确定数量的独立实验；"
    "D03/D04为重复句不计两项；'numerous'是否充分支持需共同确认；"
    "加入待共同确认清单（'It'指代IFN-I单药还是泛抗病毒治疗待裁决） |"
)
content = content.replace(old_v7_change, new_v7_change)

# 2. 4条ACCURATE中490理由（第55行附近）
old_acc_490 = (
    "**理由**：【待核】目标14只承担第二句'It has been investigated in numerous experiments both in vitro and in vivo'，"
    "不承担首句'IFN-I对MERS-CoV/SARS-CoV有活性'（首句引other_cit），也不要求单药或结果全部阳性。"
    "实验计数按原候选：in vitro 2项——D01:S02（FDA批准疗法含IFNb体外抗MERS-CoV活性评估）、"
    "D07:S01（RDV+IFNb vs LPV+RTV体外抗病毒活性比较）；"
    "in vivo 2项——D03:S01与D04:S01为完全重复句（'RDV provides su"
)
# 这个可能截断了，用更短的匹配
old_acc_490_short = "实验计数按原候选：in vitro 2项——D01:S02"
new_acc_490_short = "原候选有in vitro和in vivo相关提及，但概述句、结果句及试验目的句不足以直接合计为确定数量的独立实验；D03:S01与D04:S01为重复句不计两项；'numerous experiments'是否充分支持需共同确认，本轮不预设确定计数。待确认点：claim中'It'指代"
content = content.replace(old_acc_490_short, new_acc_490_short)

# 3. 4条待核中490理由（第72行附近）
old_pending_490 = "实验计数按原候选：in vitro 2项——D01:S02（FDA批准疗法含IFNb体外抗MERS-CoV活性评估）、D07:S01（RDV+IFNb vs LPV+RTV体外抗病毒活性比较）；in vivo 2项——D03:S01与D04:S01为完全重复句（'RDV provides superior antiviral activity against MERS-CoV in vitro and in vivo as compared with LPV/RTV-IFNb'）计1项、D"
new_pending_490 = "原候选有in vitro相关提及（D01:S02含IFNb体外评估、D07:S01含RDV与IFNb体外比较）和in vivo相关提及（D03:D04重复概述句、D04:S02 MIRACLE试验），但概述句、结果句及试验目的句不足以直接合计为确定数量的独立实验；D03:S01与D04:S01文本完全一致为重复句不计两项；'numerous experiments'是否充分支持需共同确认，本轮不预设确定计数。待确认点：claim中'It'指代D"
content = content.replace(old_pending_490, new_pending_490)

# 4. 标题37条改38条
content = content.replace("## 其余37条NOT_ACCURATE", "## 其余38条NOT_ACCURATE")

# 5. 待共同裁决事项中490描述
old_adj = "1. **490实验计数与指代**：4项实验计数已补依据，但claim中'It'指代IFN-I单药还是泛抗MERS-CoV治疗需共同确认；若限定IFN-I单药，D03/D04（RDV）和D04:S02（组合疗法）是否计入需裁决。"
new_adj = "1. **490实验计数与指代**：原候选有in vitro和in vivo相关提及，但概述句、结果句及MIRACLE试验目的句不足以直接合计为确定数量的独立实验；D03/D04为重复句不计两项；'numerous experiments'是否充分支持需共同确认；claim中'It'指代IFN-I单药还是泛抗MERS-CoV治疗需共同确认；若限定IFN-I单药，D03/D04（RDV相关）和D04:S02（组合疗法）是否计入需裁决。"
content = content.replace(old_adj, new_adj)

with open(MD, "w", encoding="utf-8") as f:
    f.write(content)

print("MD已修正：490理由去掉确定计数、37条改38条")

# 验证
with open(CSV, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("claim_id", "") == "490":
            r = row["chen_reason"]
            print(f"\n验证CSV 490理由长度: {len(r)}")
            print(f"含'4项实验': {'4项实验' in r}")
            print(f"含'不预设确定计数': {'不预设确定计数' in r}")
            break

with open(MD, "r", encoding="utf-8") as f:
    c = f.read()
    print(f"\n验证MD含'其余38条': {'其余38条' in c}")
    print(f"验证MD含'其余37条': {'其余37条' in c}")
    print(f"验证MD含'4项实验计数已补依据': {'4项实验计数已补依据' in c}")
