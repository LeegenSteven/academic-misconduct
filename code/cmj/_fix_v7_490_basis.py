# -*- coding: utf-8 -*-
import csv

new_basis = "原候选有体外和体内研究相关提及；重复概述句不重复计数；不预设独立实验数量；numerous支持程度及IFN-I治疗指代范围待共同确认。"

paths = [
    r"C:\Users\Administrator\Desktop\miss45_review_陈明进v7_20261022.csv",
    r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv",
]

for path in paths:
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    changed = 0
    for row in rows:
        if row.get("claim_id") == "490":
            old = row["chen_attribution_basis"]
            row["chen_attribution_basis"] = new_basis
            changed += 1
            print(f"修改: {path}")
            print(f"  旧: {old}")
            print(f"  新: {new_basis}")
    
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  已保存，修改{changed}行\n")
