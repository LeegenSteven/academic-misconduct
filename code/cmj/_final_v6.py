"""生成45条复核v6：10条理由收紧，490改ACCURATE，235/466/580标注待核"""
import csv, os

V5 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v5_20261021.csv"
V6 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v6_20261021.csv"

# v6修改：claim_id -> {field: value}
EDITS = {
    "48": {
        "chen_reason": "候选支持RAS阻断剂与ACE2表达及COVID-19风险的讨论，部分建议不要因感染担忧停药；但未直接支持'应用RAS阻断剂治疗COVID-19成为研究/应用热点'这一趋势性主张。claim只说成为应用热点，不要求候选证明临床有效性已被证实；问题在于候选未覆盖'治疗应用成为热点'本身。",
        "chen_attribution_basis": "候选支持风险讨论，未支持'治疗应用成为热点'",
        "chen_reason_codes": "CTX;RET",
        "chen_sem_subtypes": "",
        "chen_review_date": "2026-10-21",
    },
    "186": {
        "chen_reason": "候选为SUD（物质使用障碍，尤其OUD）研究，支持SUD患者COVID-19感染/不良结局风险增加；SUD是精神障碍的一个子类，候选未覆盖其他类型精神障碍。从SUD子类外推到'pre-existing mental disorders'整体构成范围过度概括。",
        "chen_attribution_basis": "SUD子类外推到精神障碍整体",
        "chen_reason_codes": "SEM;ATT",
        "chen_sem_subtypes": "对象;过度概括",
        "chen_review_date": "2026-10-21",
    },
    "235": {
        "chen_reason": "【待核】当前目标Flanagan只承担27.5%这一数字，D05:S01支持27.5%（D01:S01为27.3%）；Zachary的22%属other_cit，不由当前目标承担，不能作为当前目标NOT_ACCURATE的依据。当前目标对Flanagan数字有支持；但claim中'In the United States'与多国样本是否相符需另议，与250地理描述统一口径。",
        "chen_attribution_basis": "Flanagan 27.5%有支持；22%属other_cit；地理描述待核",
        "chen_reason_codes": "CTX",
        "chen_sem_subtypes": "",
        "chen_review_date": "2026-10-21",
    },
    "257": {
        "chen_reason": "候选支持存在positive dietary changes（D03定义positive change=更健康REAP-s，D04列出单项positive changes），但原候选未直接给出总体饮食质量分数（general diet quality）的正向变化结果。D01说饮食变化为正负混合，正负混合本身不自动反驳综合分数改善，但原候选也缺少总体分数正向变化的直接证据。'Americans'地理描述与多国样本不符另议。",
        "chen_attribution_basis": "原候选缺少总体分数正向变化证据；地理描述另议",
        "chen_reason_codes": "CTX;UNK",
        "chen_sem_subtypes": "",
        "chen_review_date": "2026-10-21",
    },
    "466": {
        "chen_reason": "【暂缓】原候选支持自闭症转录与功能通路异常（D01 RNA-Seq验证、D02模块与疾病相关）；冻结claim末尾包含被截断的'biological validation requires postmo[rtem]'，原候选无死后验证的直接讨论。但该claim存在重复拼接和截短，目标引用真实承载范围需另核，不能仅围绕截断片段诊断全文引用失实。仅就冻结截断文本而言原候选覆盖不足，不诊断真实引用。",
        "chen_attribution_basis": "claim截断/拼接，仅就冻结文本判，不诊断真实引用",
        "chen_reason_codes": "CTX;UNK",
        "chen_sem_subtypes": "",
        "chen_review_date": "2026-10-21",
    },
    "490": {
        "chen_label": "ACCURATE",
        "chen_reason": "目标14只承担第二句'It has been investigated in numerous experiments both in vitro and in vivo'，不承担首句IFN-I对MERS-CoV/SARS-CoV的活性（首句引other_cit），也不要求单药或结果全部阳性。实验计数：in vitro 2项（D01:S02 IFNb被评估、D07:S01 IFNb有体外活性）；in vivo 2项（D03/D04联合方案实验为重复句计1项、D04:S02 MIRACLE临床试验计1项）；合计4项实验，符合numerous experiments。D03:S01与D04:S01为重复句不计两项独立研究。不要求多个独立论文，也不要求单药或全部阳性。",
        "chen_attribution_basis": "in vitro 2项+in vivo 2项=4项实验，符合numerous；不要求单药/全部阳性",
        "chen_reason_codes": "",
        "chen_sem_subtypes": "",
        "chen_evidence_ids": "D01:S02;D07:S01;D03:S01;D04:S02",
        "chen_review_date": "2026-10-21",
    },
    "502": {
        "chen_reason": "claim的'The antiviral efficacy'承接前文remdesivir（RDV）。原候选D01:S01支持的是type I interferon的体内效果，不能替代RDV；D03:S01/D04:S01可支持RDV在体内（小鼠模型）抗病毒活性优于LPV/RTV-IFNb，但恒河猴RDV证据不在原候选。该句为multi_cit组，组内不同文献可能分别承担小鼠和恒河猴模型，不能仅因目标7没做恒河猴就否定整组。就原候选覆盖而言，两种模型未完整支持，属检索覆盖问题（RET）而非引用本身错误；全文有RDV小鼠结果但未进原候选。",
        "chen_attribution_basis": "原候选无RDV两种模型证据（D01为IFN-I）；multi_cit组内其他文献待核",
        "chen_reason_codes": "RET;UNK",
        "chen_sem_subtypes": "",
        "chen_review_date": "2026-10-21",
    },
    "544": {
        "chen_reason": "候选为49名黑人美国HIV患者子样本，显示COVID-19负面影响的横断关联与较低ART依从性有关（D01、D08、D09），但未提供同一人群前后纵向对比，也未覆盖全体HIV感染者。claim的'in people living with HIV'是泛化表述，从特定子样本外推构成范围过度概括；'seems to have decreased'暗示时间下降趋势，候选为单次邻近月份横断数据，不直接证明前后变化。",
        "chen_attribution_basis": "特定子样本横断关联，不能支持泛化下降趋势",
        "chen_reason_codes": "SEM;ATT",
        "chen_sem_subtypes": "对象;条件;过度概括",
        "chen_review_date": "2026-10-21",
    },
    "580": {
        "chen_reason": "【待核】目标标记只覆盖'changes in diet'子项，不承担后面的mental health和increased sedentary time。原候选D02:S01/D04:S01支持肥胖儿童/青少年饮食行为出现不利变化；原句'in children'不是字面all children，但候选对象为肥胖儿童小样本，是否可外推到一般儿童需裁决。不要求该目标同时证明心理健康内容。",
        "chen_attribution_basis": "目标只承担diet；肥胖儿童外推到in children待裁决",
        "chen_reason_codes": "CTX",
        "chen_sem_subtypes": "",
        "chen_review_date": "2026-10-21",
    },
    "600": {
        "chen_reason": "原候选D06:S02明确说'no quantitative measures of activity levels were available'（无客观定量活动测量），且样本为小样本、家长报告、意大利肥胖儿童；D04:S01/D07:S01只支持肥胖儿童/青少年活动行为不利变化。claim的'children have reduced levels of physical activity and increased sedentary behaviors'是群体性定量主张，原候选未提供客观定量活动测量；screen time也不等于全部sedentary time。全文补核有41名肥胖儿童家长报告的运动时长减少2.30h/周、屏幕时长增加4.85h/日，但未进入原模型输入，不能用于支持原模型判断，只能提示引用忠实性需另核；'children'省略obesity限定，群体外推待裁决。",
        "chen_attribution_basis": "原候选无客观定量测量；全文补核有家长报告数值但不用于原模型判断",
        "chen_reason_codes": "CTX;RET;UNK",
        "chen_sem_subtypes": "",
        "chen_review_date": "2026-10-21",
    },
}

# 读取v5
with open(V5, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

# 修改
changed = []
for row in rows:
    cid = row["claim_id"]
    if cid in EDITS:
        for k, v in EDITS[cid].items():
            row[k] = v
        changed.append(cid)

# 写v6
with open(V6, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

# 统计
na = sum(1 for r in rows if r["chen_label"] == "NOT_ACCURATE")
acc = sum(1 for r in rows if r["chen_label"] == "ACCURATE")
irr = sum(1 for r in rows if r["chen_label"] == "IRRELEVANT")
pending = [cid for cid in changed if "【待核】" in EDITS[cid].get("chen_reason","") or "【暂缓】" in EDITS[cid].get("chen_reason","")]

print(f"v6已生成: {V6}")
print(f"修改条目: {', '.join(changed)}")
print(f"分布: {na} NOT_ACCURATE / {acc} ACCURATE / {irr} IRRELEVANT")
print(f"待核/暂缓标注: {', '.join(pending)}")
print(f"文件大小: {os.path.getsize(V6)} bytes")
