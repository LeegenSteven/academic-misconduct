import csv
V5 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v5_20261021.csv"
with open(V5, "r", encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    print("FIELDS:", r.fieldnames)
    print()
    targets = {"48","186","235","257","466","490","502","544","580","600"}
    for row in r:
        if row["claim_id"] in targets:
            print(f"=== {row['claim_id']} ===")
            for k in r.fieldnames:
                v = row.get(k, "")
                if v:
                    print(f"  {k}: {v[:150]}")
            print()
