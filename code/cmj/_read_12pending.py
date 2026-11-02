# -*- coding: utf-8 -*-
"""读取v7中12条新暂缓项的当前理由"""
import csv

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"
TARGETS = ["0", "15", "20", "24", "28", "44", "63", "94", "217", "243", "469", "480"]

with open(V7, "r", encoding="utf-8-sig") as f:
    rows = {r["claim_id"]: r for r in csv.DictReader(f)}

for cid in TARGETS:
    r = rows[cid]
    print(f"=== {cid} ===")
    print(f"label: {r['chen_label']}")
    print(f"evids: {r['chen_evidence_ids']}")
    print(f"codes: {r['chen_reason_codes']}")
    print(f"reason: {r['chen_reason'][:200]}")
    print()
