# -*- coding: utf-8 -*-
"""v7全面自检：编码、行数、字段、标签、证据ID、跨案例串号、乱码"""
import csv, re, sys

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"
PAYLOAD = r"C:\Users\Administrator\AppData\Local\Temp\ly_45cases_20261020\45条全量初审_20261020\miss45_payload.jsonl"

errors = []
warnings = []

# 1. 编码检查
with open(V7, "rb") as f:
    raw = f.read()
bom = raw[:3]
if bom == b"\xef\xbb\xbf":
    print("[OK] 文件有UTF-8 BOM")
else:
    errors.append("文件无UTF-8 BOM，Excel可能乱码")

# 尝试解码
try:
    raw.decode("utf-8-sig")
    print("[OK] UTF-8解码成功，无乱码字节")
except UnicodeDecodeError as e:
    errors.append(f"UTF-8解码失败: {e}")

# 2. 读取CSV
with open(V7, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

print(f"[OK] 字段数: {len(fields)}")
print(f"[OK] 数据行数: {len(rows)}")
if len(rows) != 45:
    errors.append(f"数据行数{len(rows)}≠45")

# 3. 字段完整性
required = ["claim_id", "claim_text", "gold_label", "chen_label", "chen_reason", 
            "chen_evidence_ids", "chen_reason_codes", "chen_attribution_basis",
            "chen_sem_subtypes", "chen_review_date"]
for field in required:
    if field not in fields:
        errors.append(f"缺少字段: {field}")

# 4. claim_id唯一性和连续性
ids = [r["claim_id"] for r in rows]
if len(ids) != len(set(ids)):
    errors.append("claim_id有重复")
print(f"[OK] claim_id范围: {min(ids, key=int)} ~ {max(ids, key=int)}")

# 5. 标签分布
na = sum(1 for r in rows if r["chen_label"] == "NOT_ACCURATE")
acc = sum(1 for r in rows if r["chen_label"] == "ACCURATE")
other = [r["claim_id"] for r in rows if r["chen_label"] not in ("NOT_ACCURATE", "ACCURATE")]
print(f"[OK] 标签分布: {na} NOT_ACCURATE / {acc} ACCURATE")
if other:
    errors.append(f"异常标签: {other}")
if na + acc != 45:
    errors.append(f"标签总数{na+acc}≠45")

# 6. 每条字段非空检查
empty_fields = []
for r in rows:
    for field in ["chen_label", "chen_reason", "chen_evidence_ids", "chen_reason_codes", "chen_review_date"]:
        if not r[field].strip():
            empty_fields.append(f"claim {r['claim_id']} 字段{field}为空")
if empty_fields:
    errors.append(f"空字段: {'; '.join(empty_fields[:10])}")
else:
    print("[OK] 所有必填字段非空")

# 7. 乱码字符检查（替换符、控制字符）
replacement_chars = []
control_chars = []
for r in rows:
    for field in ["chen_reason", "chen_attribution_basis", "claim_text"]:
        val = r[field]
        if "\ufffd" in val:
            replacement_chars.append(f"claim {r['claim_id']} {field}含替换符")
        # 检查异常控制字符（除了常见的\n\r\t）
        for ch in val:
            if ord(ch) < 32 and ch not in "\n\r\t":
                control_chars.append(f"claim {r['claim_id']} {field}含控制字符U+{ord(ch):04X}")
if replacement_chars:
    errors.append(f"乱码替换符: {replacement_chars[:5]}")
else:
    print("[OK] 无乱码替换符(U+FFFD)")
if control_chars:
    warnings.append(f"控制字符: {control_chars[:5]}")

# 8. 加载payload，核对证据ID是否在候选中
import json
payload_evidence = {}
with open(PAYLOAD, "r", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        cid = str(rec.get("claim_id", ""))
        inp = rec.get("original_model_input", {})
        if isinstance(inp, str):
            inp = json.loads(inp)
        cands = inp.get("candidate_evidence", [])
        payload_evidence[cid] = set(c.get("evidence_id", "") for c in cands)

# 9. 证据ID核对 + 跨案例串号排查
evidence_mismatch = []
for r in rows:
    cid = r["claim_id"]
    evids = [e.strip() for e in r["chen_evidence_ids"].split(";") if e.strip()]
    if cid in payload_evidence:
        valid = payload_evidence[cid]
        for e in evids:
            if e not in valid:
                evidence_mismatch.append(f"claim {cid}: 证据ID {e} 不在原候选中（原候选: {sorted(valid)[:5]}...）")
    else:
        warnings.append(f"claim {cid}: payload中未找到")

if evidence_mismatch:
    errors.append(f"证据ID不匹配/跨案例串号: {'; '.join(evidence_mismatch)}")
else:
    print("[OK] 所有证据ID均在原候选中，无跨案例串号")

# 10. 502专项检查
r502 = next(r for r in rows if r["claim_id"] == "502")
if "D03:S01" in r502["chen_reason"] or "D04:S01" in r502["chen_reason"]:
    errors.append("502理由中仍含D03:S01或D04:S01（跨案例串号未清除）")
else:
    print("[OK] 502理由中无D03/D04串号")
if "D03:S01" in r502["chen_evidence_ids"] or "D04:S01" in r502["chen_evidence_ids"]:
    errors.append("502 evidence_ids中仍含D03/D04")
else:
    print("[OK] 502 evidence_ids中无D03/D04")

# 11. 490专项检查
r490 = next(r for r in rows if r["claim_id"] == "490")
if "4项实验" in r490["chen_reason"] or "4 项实验" in r490["chen_reason"]:
    print("[OK] 490理由含实验计数")
else:
    errors.append("490理由中未找到实验计数")
if "重复" not in r490["chen_reason"] and "去重" not in r490["chen_reason"]:
    errors.append("490理由中未说明D03/D04去重依据")
else:
    print("[OK] 490理由含去重说明")
if "待核" not in r490["chen_reason"]:
    errors.append("490未标注待核")
else:
    print("[OK] 490已标注待核")

# 12. 待核/暂缓标注检查
pending = [r["claim_id"] for r in rows if "【待核】" in r["chen_reason"] or "【暂缓】" in r["chen_reason"]]
print(f"[OK] 待核/暂缓标注: {', '.join(pending)}")
expected_pending = {"235", "466", "490", "580"}
if set(pending) != expected_pending:
    warnings.append(f"待核标注{set(pending)}与预期{expected_pending}不一致")

# 13. 理由长度检查（过短可能遗漏）
short_reasons = []
for r in rows:
    if len(r["chen_reason"]) < 30:
        short_reasons.append(f"claim {r['claim_id']}理由仅{len(r['chen_reason'])}字")
if short_reasons:
    warnings.append(f"理由过短: {'; '.join(short_reasons)}")
else:
    print("[OK] 所有理由长度≥30字")

# 14. reason_codes格式检查
bad_codes = []
valid_codes = {"SEM", "RET", "CTX", "ATT", "UNK", ""}
for r in rows:
    codes = [c.strip() for c in r["chen_reason_codes"].split(";") if c.strip()]
    for c in codes:
        if c not in valid_codes:
            bad_codes.append(f"claim {r['claim_id']}: 无效原因码{c}")
if bad_codes:
    errors.append(f"无效原因码: {'; '.join(bad_codes)}")
else:
    print("[OK] 所有原因码有效")

# 15. review_date检查
dates = set(r["chen_review_date"] for r in rows)
print(f"[OK] review_date: {', '.join(sorted(dates))}")

print()
print("=" * 50)
if errors:
    print(f"❌ 发现 {len(errors)} 个错误:")
    for e in errors:
        print(f"  - {e}")
else:
    print("✅ 无错误")
if warnings:
    print(f"⚠️  {len(warnings)} 个警告:")
    for w in warnings:
        print(f"  - {w}")
else:
    print("✅ 无警告")
