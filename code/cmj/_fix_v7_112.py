# -*- coding: utf-8 -*-
"""修正v7中112的evidence_ids字段"""
import csv

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

with open(V7, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

for r in rows:
    if r["claim_id"] == "112":
        old = r["chen_evidence_ids"]
        r["chen_evidence_ids"] = "D01:S01;D02:S01;D03:S01;D03:S02"
        print(f"112 evidence_ids: {old} -> {r['chen_evidence_ids']}")

with open(V7, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("v7已更新")
