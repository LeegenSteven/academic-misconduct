# -*- coding: utf-8 -*-
"""v7整合：更新12条新暂缓项的收紧理由"""
import csv

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

EDITS = {
    "0": {
        "chen_reason": "候选支持TMAO通路（饮食→肠道菌群→TMA/TMAO→动脉粥样硬化）：D06提及其他膳食营养素可能生成TMAO促进动脉粥样硬化，D07支持L-carnitine可能产生TMA/TMAO与动脉粥样硬化风险相关，D09支持血浆肉碱与心血管风险关联。但FMO3作为该通路关键组成部分无直接证据——候选仅提及FMOs酶家族，未精确到FMO3。该句为multi_cit引用组，FMO3特异证据可能由组内其他文献承担；当前目标候选未覆盖FMO3特异部分。",
        "chen_attribution_basis": "候选支持TMAO通路但FMO3特异证据缺失；FMO3可能由引用组其他文献承担",
        "chen_reason_codes": "CTX;ATT;UNK",
        "chen_evidence_ids": "D06:S02;D07:S01;D09:S01",
    },
    "15": {
        "chen_reason": "claim精确列出MS4A6A和MS4A4E两个具体基因名。候选支持MS4A区域与LOAD关联：D02:S01列10个易感位点含MS4A（cluster层面），D02:S02提到MS4A4A，D07:S01标题为MS4A4/MS4A6E。但没有候选句精确对应MS4A6A/MS4A4E的具体基因名——MS4A4A≠MS4A4E，MS4A6E≠MS4A6A。该句为multi_cit引用组，具体基因成员可能由组内其他文献承担；当前目标候选未精确覆盖两个具体基因名。",
        "chen_attribution_basis": "候选支持MS4A区域但未精确对应MS4A6A/MS4A4E具体基因名；具体成员可能由引用组其他文献承担",
        "chen_reason_codes": "CTX;ATT;UNK",
        "chen_evidence_ids": "D02:S01;D02:S02;D07:S01",
    },
    "20": {
        "chen_reason": "九项位点列表有支持：D01列10个LOAD易感位点含APOE，去掉APOE即为9项（CLU/PICALM/CR1/BIN1/MS4A/ABCA7/CD33/EPHA1/CD2AP）。但claim含'within the past 3 years'时间限定，候选未明确给出该时间范围。该句为多研究引用组（Harold/Lambert/Seshadri/Hollingworth/Naj），不能要求单篇候选给出全部研究的时间戳；当前目标候选未覆盖时间限定部分。",
        "chen_attribution_basis": "位点列表有支持，'within past 3 years'时间限定候选未覆盖；多研究引用组不能要求单篇给时间戳",
        "chen_reason_codes": "CTX;ATT;UNK",
        "chen_evidence_ids": "D01:S01;D02:S01;D05:S01",
    },
    "24": {
        "chen_reason": "候选支持部分位点与LOAD关联并有重复验证：D01列10个易感位点，D03支持Stage 1+2确认BIN1/CR1/CLU/PICALM，D06给出CR1/CLU/BIN1/PICALM的P值。但claim要求'significant association after multiple test correction in multiple datasets'逐项适用于全部8个基因，候选未逐项证明每个基因都满足多数据集多重检验校正后显著——ABCA7/MS4A6A/CD33/CD2AP的校正后显著性在当前候选中未完整覆盖。",
        "chen_attribution_basis": "部分位点有显著P值及重复分析，但未逐项证明每个基因都满足多数据集校正后显著",
        "chen_reason_codes": "CTX;ATT;UNK",
        "chen_evidence_ids": "D01:S01;D01:S02;D03:S01;D06:S01",
    },
    "28": {
        "chen_reason": "九项位点数量不矛盾（9个新位点vs10个总位点含APOE）。但claim明确列出5篇研究（Harold/Lambert/Seshadri/Hollingworth/Naj）的合并总结，当前候选主要来自Naj和Hollingworth，不能由单篇候选充分覆盖5篇研究的合并结论。该句为multi_cit引用组，5篇研究各自的贡献可能由组内不同文献分别承担；当前目标候选未完整覆盖5篇合并总结。",
        "chen_attribution_basis": "九项位点数量不矛盾；五篇研究的合并总结不能由当前候选单篇充分覆盖",
        "chen_reason_codes": "CTX;ATT;UNK",
        "chen_evidence_ids": "D01:S01;D05:S01;D07:S01;D08:S01",
    },
    "44": {
        "chen_reason": "候选未直接列出'65个index SNPs'这一具体数字。D01提及77个transcripts为不同口径（转录本数≠index SNP数），不能作数值对照；D06讨论mixture model未纳入某些位点。65与全文中63的集合关系及性别分层需逐个对齐SNP列表，但当前候选未提供65个index SNP的直接证据。",
        "chen_attribution_basis": "候选未直接列65个index SNPs；77个transcripts为不同口径不能作数值对照",
        "chen_reason_codes": "CTX;RET;UNK",
        "chen_evidence_ids": "D02:S01;D06:S01;D07:S01",
    },
    "63": {
        "chen_reason": "'most of them are review or opinion articles'是关于整个领域文献数量分布的元论断。候选为单篇commentary（D03）讨论ACE-I/ARB与ACE2表达的证据不足，D06说无数据支持ACE-I/ARB增加ACE2表达。单篇commentary不能证明'大多数文献为综述或观点文章'这一文献分布论断——候选本身是commentary，但不代表领域多数文献都是综述/观点。",
        "chen_attribution_basis": "候选为单篇commentary，不能证明'大多数文献为综述'的文献分布论断",
        "chen_reason_codes": "ATT;CTX;UNK",
        "chen_evidence_ids": "D01:S01;D03:S01;D06:S01",
    },
    "94": {
        "chen_reason": "候选记录旧实验阴性结果本身：D02:S01显示HeLa内源PARL检测不到但shRNA抑制过表达PARL，D02:S02显示PARL敲低不改变PINK1水平，D02:S04显示PARL-/- MEF中PINK1水平与WT相似。但claim是施引作者对阴性结果的解释——'insufficient knockdown/insufficient expression'，候选未直接支持该解释。引用旧工作可能用于定位被解释的旧结果，未必声称旧论文已承认该解释；当前候选仅记录阴性结果，不支持解释部分。",
        "chen_attribution_basis": "候选记录阴性结果本身，但施引作者'敲低不足/表达不足'的解释未被直接支持",
        "chen_reason_codes": "CTX;SEM",
        "chen_evidence_ids": "D02:S01;D02:S02;D02:S04",
    },
    "217": {
        "chen_reason": "候选支持疫情期间饮食行为有变化：D02说明评估饮食行为变化，D08列出总体变化图（REAP-s），D04说'abrupt changes'导致心理健康下降及正负行为变化。但claim说'small changes'（幅度小），候选没有直接支持变化幅度小——abrupt描述发生速度不直接反驳幅度小，overall changes描述存在变化不说明幅度。全文REAP-s总分从18.3至19.1变化约0.81，可能算小幅，但未进入原模型输入，不能用于支持原模型判断。",
        "chen_attribution_basis": "候选支持饮食有变化，但'small'幅度无直接证据；全文REAP-s变化0.81未进原候选",
        "chen_reason_codes": "CTX;RET;UNK",
        "chen_evidence_ids": "D02:S01;D03:S01;D04:S01;D08:S01",
    },
    "243": {
        "chen_reason": "'Much of the research has been conducted outside the U.S.'是关于整个领域文献数量分布的论断。候选D01说'first to survey thousands of people across the globe'（单篇全球调查），D08提及美国以外代表性国家（加拿大/英国/澳大利亚/爱尔兰）。单篇全球调查的招募国家不能证明整个领域'多数研究在美国以外'——招募地点不等于研究篇数分布。该句为multi_cit引用组，领域文献分布可能由组内其他文献承担；当前目标候选未覆盖文献分布论断。",
        "chen_attribution_basis": "候选为单篇全球调查招募国家，不能证明领域文献分布；招募地点≠研究篇数分布",
        "chen_reason_codes": "CTX;ATT",
        "chen_evidence_ids": "D01:S01;D04:S01;D08:S01",
    },
    "469": {
        "chen_reason": "目标引用在'in a manner previously described'后，承担方法描述方式。候选支持GWAS set-enrichment分析方法的存在：D01说明使用Wang et al.发现队列（AGRE）做set enrichment，D03说明阴性对照用相同set-enrichment分析，D05列出富集p值。但set-enrichment方法的具体算法实现细节（20kb/10kb边界、置换停止规则等）当前候选未完整覆盖。943家系和Wang发现队列由other_cit承担，不要求当前目标文献证明这些来源。",
        "chen_attribution_basis": "候选支持set-enrichment方法存在，但具体算法实现细节候选未完整覆盖；943家系由other_cit承担",
        "chen_reason_codes": "CTX;ATT;UNK",
        "chen_evidence_ids": "D01:S01;D02:S01;D03:S01",
    },
    "480": {
        "chen_reason": "目标引用<|cit|>承担'remdesivir治疗MERS-CoV优于LPV/RTV/IFNβ组合'。原候选D01:S01仅为比较研究标题（'Comparative therapeutic efficacy of remdesivir and combination LPV/RTV/IFNb against MERS-CoV'），未给出结果数据；D02:S01说组合疗法正在评估中；D03:S01说interferon treatment不改善临床结局及MIRACLE试验。无候选直接支持RDV优于组合的具体疗效结论。全文确有RDV体内外优越性结果，但未进入原模型输入，另列并注明模型未见。lethal SARS-CoV2部分接other_cit，不由当前目标承担。",
        "chen_attribution_basis": "原候选仅含比较研究标题及组合疗法评估讨论，未给出RDV优于组合的具体结果；全文有结果但未进原候选",
        "chen_reason_codes": "CTX;UNK",
        "chen_evidence_ids": "D01:S01;D02:S01;D03:S01;D08:S01",
    },
}

with open(V7, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

changed = []
for row in rows:
    cid = row["claim_id"]
    if cid in EDITS:
        for k, v in EDITS[cid].items():
            row[k] = v
        row["chen_review_date"] = "2026-10-22"
        changed.append(cid)

with open(V7, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

na = sum(1 for r in rows if r["chen_label"] == "NOT_ACCURATE")
acc = sum(1 for r in rows if r["chen_label"] == "ACCURATE")
print(f"v7已更新12条理由: {', '.join(changed)}")
print(f"分布: {na} NOT_ACCURATE / {acc} ACCURATE")
