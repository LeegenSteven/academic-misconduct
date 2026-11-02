# -*- coding: utf-8 -*-
"""核查112、233、490理由中额外证据ID的上下文"""
import csv

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

with open(V7, "r", encoding="utf-8-sig") as f:
    rows = {r["claim_id"]: r for r in csv.DictReader(f)}

for cid in ["112", "233", "490"]:
    r = rows[cid]
    print(f"=== claim {cid} ===")
    print(f"evidence_ids字段: {r['chen_evidence_ids']}")
    print(f"理由全文:")
    print(r["chen_reason"])
    print()
