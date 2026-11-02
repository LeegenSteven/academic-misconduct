# -*- coding: utf-8 -*-
"""生成v7：修正502跨案例串号、490实验计数补依据并加入待核"""
import csv, os

V6 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\新建文件夹\miss45_review_陈明进v6_20261021.csv"
V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

EDITS = {
    "502": {
        "chen_reason": "claim的'The antiviral efficacy'承接前文remdesivir（RDV）。原候选全部为IFN-I相关及方法学内容：D01:S01支持type I interferon体内效果（IFN alpha恒河猴、IFNb腺病毒小鼠），D02:S01为IFNb在小鼠中生物学效应，D08:S02提到小鼠模型中评估治疗方案但未给出RDV具体结果。原候选中无RDV在小鼠和恒河猴两种模型中疗效的直接证据。该句为multi_cit组，组内不同文献（原XML引用6为恒河猴RDV研究、7为小鼠研究）可能分别承担不同模型，不能仅因当前目标候选未覆盖就否定整组。全文有RDV小鼠结果但未进入原模型输入，另列并注明模型未见。",
        "chen_attribution_basis": "原候选无RDV两种模型疗效证据（D01为IFN-I）；multi_cit组内其他文献待核；全文有RDV小鼠结果但未进原候选",
        "chen_reason_codes": "RET;UNK",
        "chen_sem_subtypes": "",
        "chen_evidence_ids": "D01:S01;D02:S01;D08:S02",
        "chen_review_date": "2026-10-22",
    },
    "490": {
        "chen_reason": "【待核】目标14只承担第二句'It has been investigated in numerous experiments both in vitro and in vivo'，不承担首句'IFN-I对MERS-CoV/SARS-CoV有活性'（首句引other_cit），也不要求单药或结果全部阳性。实验计数按原候选：in vitro 2项——D01:S02（FDA批准疗法含IFNb体外抗MERS-CoV活性评估）、D07:S01（RDV+IFNb vs LPV+RTV体外抗病毒活性比较）；in vivo 2项——D03:S01与D04:S01为完全重复句（'RDV provides superior antiviral activity against MERS-CoV in vitro and in vivo as compared with LPV/RTV-IFNb'）计1项、D04:S02（MIRACLE临床试验评估LPV/RTV-IFNb组合疗法）；合计4项实验。D03:S01与D04:S01文本完全一致，去重依据为逐字相同，不计两项独立研究。待确认点：claim中'It'指代IFN-I单药还是泛抗MERS-CoV治疗；若限定IFN-I单药，则D03/D04（RDV）和D04:S02（组合疗法）是否计入需共同裁决。不要求多个独立论文，也不要求单药或全部阳性。",
        "chen_attribution_basis": "in vitro 2项+in vivo 2项=4项实验，D03/D04逐字重复去重；'It'指代待共同确认",
        "chen_reason_codes": "CTX;UNK",
        "chen_sem_subtypes": "",
        "chen_evidence_ids": "D01:S02;D07:S01;D03:S01;D04:S02",
        "chen_review_date": "2026-10-22",
    },
}

with open(V6, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

changed = []
for row in rows:
    cid = row["claim_id"]
    if cid in EDITS:
        for k, v in EDITS[cid].items():
            row[k] = v
        changed.append(cid)

with open(V7, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

na = sum(1 for r in rows if r["chen_label"] == "NOT_ACCURATE")
acc = sum(1 for r in rows if r["chen_label"] == "ACCURATE")
pending = [r["claim_id"] for r in rows if "【待核】" in r["chen_reason"] or "【暂缓】" in r["chen_reason"]]

print(f"v7已生成: {V7}")
print(f"修改条目: {', '.join(changed)}")
print(f"分布: {na} NOT_ACCURATE / {acc} ACCURATE")
print(f"待核/暂缓标注: {', '.join(pending)}")
print(f"文件大小: {os.path.getsize(V7)} bytes")
