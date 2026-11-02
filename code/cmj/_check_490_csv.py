# -*- coding: utf-8 -*-
import csv

path = r"C:\Users\Administrator\Desktop\miss45_review_陈明进v7_20261022.csv"
with open(path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    print("列名:", reader.fieldnames)
    print()
    for row in reader:
        if row.get("claim_id") == "490" or row.get("id") == "490" or "490" in row.get("claim_id", ""):
            print("找到490行:")
            for k, v in row.items():
                if v and ("4" in v or "实验" in v or "attribution" in k.lower() or "basis" in k.lower()):
                    print(f"  {k}: {v[:200]}")
            break
