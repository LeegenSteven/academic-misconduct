# -*- coding: utf-8 -*-
import csv

path = r"C:\Users\Administrator\Desktop\miss45_review_陈明进v7_20261022.csv"
with open(path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("claim_id") == "250":
            print("claim_id:", row["claim_id"])
            print("chen_label:", row["chen_label"])
            print("chen_reason:", row["chen_reason"][:500])
            print("chen_attribution_basis:", row["chen_attribution_basis"])
            print("resolved_label:", row["resolved_label"])
            print("review_status:", row["review_status"])
            break
