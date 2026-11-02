# -*- coding: utf-8 -*-
"""验证v7中502和490的修改"""
import csv

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

with open(V7, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["claim_id"] in ["502", "490"]:
            print(f"=== claim {row['claim_id']} ===")
            print(f"label: {row['chen_label']}")
            print(f"evidence_ids: {row['chen_evidence_ids']}")
            print(f"reason_codes: {row['chen_reason_codes']}")
            print(f"reason: {row['chen_reason'][:300]}")
            print()
