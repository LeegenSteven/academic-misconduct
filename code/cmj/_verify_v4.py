"""45条终版v4全面自检。"""
import csv, json, os, hashlib

OUT_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核"
CSV_PATH = os.path.join(OUT_DIR, "miss45_review_陈明进终版v4_20261020.csv")
MD_PATH = os.path.join(OUT_DIR, "45条三方对比与分歧裁决_陈明进_终版v4_20261020.md")

def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition

print("=" * 60)
print("1. 文件存在性与编码")
print("=" * 60)
for p, name in [(CSV_PATH, "CSV"), (MD_PATH, "MD")]:
    exists = os.path.exists(p)
    if exists:
        size = os.path.getsize(p)
        with open(p, "rb") as f:
            head = f.read(3)
        bom = "UTF-8-BOM" if head == b"\xef\xbb\xbf" else "UTF-8"
        check(f"{name}存在且非空", size > 0, f"{size:,} bytes, {bom}")
    else:
        check(f"{name}存在", False, "文件不存在")

print()
print("=" * 60)
print("2. CSV 结构与完整性")
print("=" * 60)
with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

check("CSV行数=45", len(rows) == 45, f"实际{len(rows)}")
check("CSV列数=42", len(fieldnames) == 42, f"实际{len(fieldnames)}")
check("无乱码替换字符", all("\ufffd" not in json.dumps(r, ensure_ascii=False) for r in rows))

# 标签分布
from collections import Counter
labels = Counter(r["chen_label"] for r in rows)
check("分布=40 NOT_ACCURATE + 5 ACCURATE",
      labels.get("NOT_ACCURATE") == 40 and labels.get("ACCURATE") == 5,
      f"实际{dict(labels)}")

# claim_id唯一且连续
claim_ids = [r["claim_id"] for r in rows]
check("45个claim_id唯一", len(set(claim_ids)) == 45)
check("claim_id均为字符串", all(isinstance(cid, str) for cid in claim_ids))

print()
print("=" * 60)
print("3. v4修正条目验证（20/28/490/502）")
print("=" * 60)
v4_targets = {
    "20": {"must_contain": ["within the past 3 years", "时间限定"], "must_not": ["单篇Naj"]},
    "28": {"must_contain": ["Harold", "Lambert", "Seshadri", "Hollingworth", "Naj"], "must_not": []},
    "490": {"must_contain": ["IFN单药", "联合方案", "numerous", "in vitro", "in vivo"], "must_not": ["仅支持in vitro评估，无numerous in vivo"]},
    "502": {"must_contain": ["remdesivir", "RDV", "IFN", "指代"], "must_not": ["未指定药物", "归属不明"]},
}
for cid, checks in v4_targets.items():
    r = next(x for x in rows if x["claim_id"] == cid)
    text = r["chen_reason"] + r["chen_attribution_basis"]
    for kw in checks["must_contain"]:
        check(f"claim {cid} reason/归因含'{kw}'", kw in text)
    for kw in checks["must_not"]:
        check(f"claim {cid} 不含旧文字'{kw}'", kw not in text)

print()
print("=" * 60)
print("4. v3修正条目保持验证（233/242/480）")
print("=" * 60)
v3_targets = {
    "233": {"label": "NOT_ACCURATE", "must_contain": ["D04:S03不在本条候选", "多国样本", "美国"]},
    "242": {"label": "NOT_ACCURATE", "must_contain": ["健康饮食", "This increase", "非体重增加"]},
    "480": {"label": "NOT_ACCURATE", "must_contain": ["MERS-CoV", "比较疗效"]},
}
for cid, checks in v3_targets.items():
    r = next(x for x in rows if x["claim_id"] == cid)
    check(f"claim {cid} label={checks['label']}", r["chen_label"] == checks["label"], f"实际{r['chen_label']}")
    text = r["chen_reason"] + r["chen_attribution_basis"]
    for kw in checks["must_contain"]:
        check(f"claim {cid} 含'{kw}'", kw in text)

print()
print("=" * 60)
print("5. 5条ACCURATE验证（112/120/138/236/342）")
print("=" * 60)
accurate_ids = ["112", "120", "138", "236", "342"]
for cid in accurate_ids:
    r = next(x for x in rows if x["claim_id"] == cid)
    check(f"claim {cid} label=ACCURATE", r["chen_label"] == "ACCURATE", f"实际{r['chen_label']}")
    check(f"claim {cid} reason含'改判'", "改判" in r["chen_reason"])
    check(f"claim {cid} 归因列非空", bool(r["chen_attribution_basis"].strip()))
    check(f"claim {cid} reason_codes为空", r["chen_reason_codes"] == "")

print()
print("=" * 60)
print("6. 归因列全面扫描（无旧文字残留）")
print("=" * 60)
old_patterns = ["单篇Naj", "D04:S03", "未指定药物", "归属不明", "仅支持in vitro评估，无numerous in vivo"]
for r in rows:
    cid = r["claim_id"]
    attr = r["chen_attribution_basis"]
    reason = r["chen_reason"]
    for pat in old_patterns:
        # claim 28的归因可以包含"Naj"但不是"单篇Naj"
        if pat == "单篇Naj" and cid == "28":
            continue
        if pat in attr or (pat in reason and cid not in ["490", "502"]):
            check(f"claim {cid} 不含旧文字'{pat}'", False, f"出现在reason/归因")

print("  扫描完成（无输出即全部通过）")

print()
print("=" * 60)
print("7. MD报告验证")
print("=" * 60)
with open(MD_PATH, "r", encoding="utf-8") as f:
    md = f.read()

check("MD含'终版v4'", "终版v4" in md)
check("MD含个人意见标注", "个人复核意见" in md and "待双方确认" in md)
check("MD含v4修正记录（20/28/490/502）",
      all(x in md for x in ["claim 20", "claim 28", "claim 490", "claim 502", "v4新增"]))
check("MD含v3修正记录（233/242/480）",
      all(x in md for x in ["claim 233", "claim 242", "claim 480"]))
check("MD分布=40/5", "40" in md and "5" in md and "88.9%" in md and "11.1%" in md)
check("MD含5条gold差异列表", all(f"claim {x}" in md for x in accurate_ids))
check("MD含250分歧保留", "250" in md and "地理描述" in md)
check("MD无乱码", "\ufffd" not in md)
check("MD含冻结Test成绩保持原口径", "冻结Test成绩保持原口径" in md)

print()
print("=" * 60)
print("8. CSV与MD一致性")
print("=" * 60)
# 分布一致
check("CSV与MD分布一致", "40 NOT_ACCURATE" in md or "NOT_ACCURATE | 40" in md)
# 修正条目在两者中都有
for cid in ["20", "28", "490", "502", "233", "242", "480"]:
    check(f"claim {cid} 在CSV和MD中均有记录", f"claim {cid}" in md)

print()
print("=" * 60)
print("9. 关键字段非空检查")
print("=" * 60)
required_fields = ["chen_label", "chen_reason", "chen_attribution_basis", "chen_evidence_ids", "chen_review_date"]
empty_count = 0
for r in rows:
    for fld in required_fields:
        if not r.get(fld, "").strip():
            empty_count += 1
            print(f"    claim {r['claim_id']} 字段{fld}为空")
check("全部45条关键字段非空", empty_count == 0, f"空字段{empty_count}个")

print()
print("=" * 60)
print("自检完成")
print("=" * 60)
