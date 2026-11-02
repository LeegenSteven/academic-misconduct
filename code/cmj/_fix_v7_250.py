# -*- coding: utf-8 -*-
import csv

new_label = "ACCURATE"
new_reason = "候选D03:S01直接支持早餐跳过频率降低的方向性结论；D04:S03说明全样本结论与美国亚组未见差异，方向性结论在美国亚组同样成立。claim中'in a study conducted in the United States'为范围限定语，研究实际包含多国参与者（美/澳/加/爱/英），该表述不够精确，但不改变核心结论方向。与235条不同：235是具体数值被错误归为美国结果的数值归属错误；250是方向性结论且有美国亚组数据支持方向一致性，地域简化不构成影响核心结论的重要范围错误。限制：D04:S03的'未见差异'仅说明方向一致，不视为统计等效或逐项数值相同。经双方共同裁决由NOT_ACCURATE改为ACCURATE。"
new_basis = "早餐跳过减少有D03:S01直接支持；研究实际为多国非纯美国，但D04:S03显示全样本与美国亚组方向一致；地域限定不够精确但不影响核心方向性结论；与235数值归属错误不同"
new_resolved = "ACCURATE"
new_status = "resolved"

paths = [
    r"C:\Users\Administrator\Desktop\miss45_review_陈明进v7_20261022.csv",
    r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv",
]

for path in paths:
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    for row in rows:
        if row.get("claim_id") == "250":
            row["chen_label"] = new_label
            row["chen_reason"] = new_reason
            row["chen_attribution_basis"] = new_basis
            row["resolved_label"] = new_resolved
            row["review_status"] = new_status
            print(f"已修改: {path}")
            print(f"  label: {new_label}")
            print(f"  resolved: {new_resolved}")
            print(f"  status: {new_status}")
    
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# 统计最终分布
with open(paths[0], "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    acc = sum(1 for r in rows if r["chen_label"] == "ACCURATE")
    na = sum(1 for r in rows if r["chen_label"] == "NOT_ACCURATE")
    irr = sum(1 for r in rows if r["chen_label"] == "IRRELEVANT")
    print(f"\n最终分布: ACCURATE={acc}, NOT_ACCURATE={na}, IRRELEVANT={irr}, 总计={len(rows)}")
