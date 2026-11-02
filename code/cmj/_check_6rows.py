# -*- coding: utf-8 -*-
import csv

path = r"C:\Users\Administrator\Desktop\miss45_review_陈明进v7_20261022.csv"
with open(path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cid = row.get("claim_id", "")
        if cid in ("235", "236", "342", "466", "490", "580"):
            print(f"=== claim {cid} ===")
            print(f"  chen_label: {row['chen_label']}")
            print(f"  chen_reason: {row['chen_reason'][:300]}")
            print(f"  chen_attribution_basis: {row['chen_attribution_basis']}")
            print(f"  review_status: {row['review_status']}")
            print()
