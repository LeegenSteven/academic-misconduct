# -*- coding: utf-8 -*-
import csv, io, os

csv_path = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

with open(csv_path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
    fields = list(rows[0].keys())

reason = (
    "【恢复句限定性ACCURATE·原冻结claim暂缓】2026-10-23补充核验：恢复后第二句"
    "\"The comparison of findings between the present study and Voineagu et al. [20] "
    "demonstrates a consistent overlap involving several pathways including repair- "
    "and immune-related processes\"。施引PMC3310790 Results跨研究比较小节"
    "（body/sec[2]/sec[4]/p1-p2）：p1说明将本研究诊断主效应基因与Voineagu et al. [20]"
    "差异表达基因比较；p2报告25个p<0.05重叠探针（p<0.0001），其中6个Tissue Remodeling "
    "and Wound Repair基因（p=1.622E-4, FDR<0.05）、7个Immune System Response基因"
    "（p=4.772E-4, FDR<0.05），并概括\"some consistency...particularly within domains "
    "of repair and immune response\"；Discussion目标句即该小节概括。被引PMC3607626可定位"
    "免疫/炎症富集（N=235上调基因富集immune/inflammatory GO）；修复归类来自施引作者自己的"
    "跨研究MetaCore分析，不要求被引正文预先使用repair分类名，也不谎称被引正文写了repair。"
    "限制：①仅对恢复后第二句的作者报告性比较给限定性ACCURATE，不替残缺冻结claim补出原模型"
    "已见证据；②本轮未独立重做25探针匹配、富集分析及两篇基因列表计算，不是数据层面复现；"
    "③原冻结残缺输入、NOT_ACCURATE gold、两模型预测、Test分母与成绩全部保留；④本意见为"
    "诊断性个人意见，不是双方三分类最终裁决，原冻结claim三分类仍暂缓；⑤\"consistent\"对应"
    "Results\"some consistency\"，强度差异属施引作者Discussion自身概括，不构成核心歪曲。"
)

basis = (
    "恢复句比较动作、25探针重叠、6修复/7免疫基因及富集显著性均由施引Results直接报告，"
    "Discussion概括忠实；免疫方向可定位被引，修复归类来自施引自己的跨研究分析；"
    "仅诊断性个人意见，原冻结claim暂缓，gold/Test/模型预测不改。"
)

updated = False
for row in rows:
    if row["claim_id"] == "466":
        row["chen_label"] = "ACCURATE"
        row["chen_evidence_ids"] = "D01:S01;D02:S01;D04:S01"
        row["chen_reason"] = reason
        row["chen_review_date"] = "2026-10-23"
        row["chen_reason_codes"] = "CTX"
        row["chen_attribution_basis"] = basis
        row["review_status"] = "pending_two_reviews"
        row["resolved_label"] = ""
        row["resolved_reason"] = ""
        updated = True
        break

assert updated, "466 row not found"

with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

# 回读校验
with open(csv_path, encoding="utf-8-sig", newline="") as f:
    r2 = list(csv.DictReader(f))
for row in r2:
    if row["claim_id"] == "466":
        print("chen_label:", row["chen_label"])
        print("review_status:", row["review_status"])
        print("resolved_label:", repr(row["resolved_label"]))
        print("chen_review_date:", row["chen_review_date"])
        print("gold:", row["gold"], "| M0:", row["M0_pred"], "| Mbio:", row["Mbio_pred"])
        print("reason_len:", len(row["chen_reason"]))
import collections
print("chen_label分布:", dict(collections.Counter(x["chen_label"] for x in r2)))
print("总行数:", len(r2))
