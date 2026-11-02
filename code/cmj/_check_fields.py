# -*- coding: utf-8 -*-
"""检查v6字段名和ACCURATE条目的reason_codes"""
import csv

V6 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\新建文件夹\miss45_review_陈明进v6_20261021.csv"
V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

for path, name in [(V6, "v6"), (V7, "v7")]:
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    print(f"=== {name} ===")
    print(f"字段({len(fields)}): {fields}")
    # 找gold相关字段
    gold_fields = [f for f in fields if "gold" in f.lower() or "label" in f.lower()]
    print(f"gold/label相关字段: {gold_fields}")
    # ACCURATE条目的reason_codes
    acc = [r for r in rows if r["chen_label"] == "ACCURATE"]
    for r in acc:
        print(f"  claim {r['claim_id']}: reason_codes='{r['chen_reason_codes']}'")
    print()
