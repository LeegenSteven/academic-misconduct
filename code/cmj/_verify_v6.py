"""v6交付自检：验证10条修改、分布、待核标注、490改判"""
import csv

V6 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v6_20261021.csv"

with open(V6, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

print("=== v6自检 ===")
print(f"总行数: {len(rows)} (期望45)")

# 分布
na = [r for r in rows if r["chen_label"] == "NOT_ACCURATE"]
acc = [r for r in rows if r["chen_label"] == "ACCURATE"]
print(f"分布: {len(na)} NA / {len(acc)} ACC (期望41/4)")

# 4条ACCURATE
acc_ids = sorted([r["claim_id"] for r in acc])
print(f"ACCURATE条目: {acc_ids} (期望138,236,342,490)")

# 490改判
r490 = [r for r in rows if r["claim_id"] == "490"][0]
print(f"\n490标签: {r490['chen_label']} (期望ACCURATE)")
print(f"490理由含'4项实验': {'4项实验' in r490['chen_reason']}")
print(f"490理由含'重复句': {'重复句' in r490['chen_reason']}")

# 待核/暂缓标注
pending = [r["claim_id"] for r in rows if "【待核】" in r["chen_reason"] or "【暂缓】" in r["chen_reason"]]
print(f"\n待核/暂缓标注: {pending} (期望235,466,580)")

# 10条理由检查
checks = {
    "48": ("疗效" not in [r for r in rows if r["claim_id"]=="48"][0]["chen_reason"], "去掉'疗效'前提"),
    "186": ("所有" not in [r for r in rows if r["claim_id"]=="186"][0]["chen_reason"], "去掉'所有'"),
    "235": ("other_cit" in [r for r in rows if r["claim_id"]=="235"][0]["chen_reason"], "22%属other_cit"),
    "257": ("总体分数" in [r for r in rows if r["claim_id"]=="257"][0]["chen_reason"], "改为总体分数证据"),
    "466": ("截断" in [r for r in rows if r["claim_id"]=="466"][0]["chen_reason"], "标注截断"),
    "502": ("RET" in [r for r in rows if r["claim_id"]=="502"][0]["chen_reason"], "区分RET"),
    "544": ("所有" not in [r for r in rows if r["claim_id"]=="544"][0]["chen_reason"], "去掉'所有'"),
    "580": ("diet" in [r for r in rows if r["claim_id"]=="580"][0]["chen_reason"], "目标只承担diet"),
    "600": ("客观定量" in [r for r in rows if r["claim_id"]=="600"][0]["chen_reason"], "改为无客观定量测量"),
}
print("\n10条理由检查:")
all_pass = True
for cid, (cond, desc) in checks.items():
    status = "PASS" if cond else "FAIL"
    if not cond: all_pass = False
    print(f"  {cid}: {status} - {desc}")

# 日期更新
dated = [r["claim_id"] for r in rows if r["chen_review_date"] == "2026-10-21"]
print(f"\n日期更新为10-21的条目: {len(dated)}条 (期望10条)")

# 其余35条未改动
unchanged = [r["claim_id"] for r in rows if r["chen_review_date"] == "2026-10-20"]
print(f"日期保持10-20的条目: {len(unchanged)}条 (期望35条)")

print(f"\n{'全部通过' if all_pass and len(rows)==45 and len(acc)==4 and len(pending)==3 else '存在问题'}")
