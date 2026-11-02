"""v5全面自检"""
import csv, os
from collections import Counter

d = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核"
csv_p = os.path.join(d, "miss45_review_陈明进v5_20261021.csv")
md_p = os.path.join(d, "45条三方对比与分歧裁决_陈明进_v5_20261021.md")

with open(csv_p, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

print("=== CSV结构 ===")
print("行数:", len(rows), "(期望45)")
print("列数:", len(rows[0].keys()), "(期望42)")
labels = Counter(r["chen_label"] for r in rows)
print("分布:", dict(labels), "(期望42 NOT_ACCURATE / 3 ACCURATE)")
print("无乱码:", all("\ufffd" not in str(r) for r in rows))

print()
print("=== v5修正条目验证 ===")
targets = {
    "112": {"label": "NOT_ACCURATE", "must": ["viral variants", "恒河猴"]},
    "120": {"label": "NOT_ACCURATE", "must": ["recovery", "long-term immunity", "恒河猴"]},
    "233": {"label": "NOT_ACCURATE", "must": ["D04:S03", "不在原候选", "引用范围"]},
    "242": {"label": "NOT_ACCURATE", "must": ["one-quarter", "容差"]},
    "490": {"label": "NOT_ACCURATE", "must": ["口径", "numerous", "重复句"]},
}
for cid, checks in targets.items():
    r = next(x for x in rows if x["claim_id"] == cid)
    ok_label = r["chen_label"] == checks["label"]
    text = r["chen_reason"] + r["chen_attribution_basis"]
    ok_kw = all(kw in text for kw in checks["must"])
    status = "OK" if (ok_label and ok_kw) else "FAIL"
    print(f"  claim {cid}: [{status}] label={r['chen_label']}")
    if not ok_kw:
        for kw in checks["must"]:
            if kw not in text:
                print(f"    缺少: {kw}")

print()
print("=== 3条ACCURATE验证 ===")
for cid in ["138", "236", "342"]:
    r = next(x for x in rows if x["claim_id"] == cid)
    print(f"  claim {cid}: {r['chen_label']}")

print()
print("=== MD报告验证 ===")
with open(md_p, "r", encoding="utf-8") as f:
    md = f.read()
checks = [
    ("含v5", "v5" in md),
    ("含个人意见标注", "个人复核意见" in md and "待双方共同裁决" in md),
    ("分布42/3", "42" in md and "93.3%" in md),
    ("含112/120改判", "claim 112" in md and "claim 120" in md),
    ("含490口径选择", "口径选择" in md),
    ("含233引用范围", "引用范围" in md),
]
for name, ok in checks:
    print(f"  [{ 'OK' if ok else 'FAIL'}] {name}")

print()
print("文件大小:")
print("  CSV:", os.path.getsize(csv_p), "bytes")
print("  MD:", os.path.getsize(md_p), "bytes")
print()
print("自检完成")
