# -*- coding: utf-8 -*-
"""逐条检查v7理由与claim的相关性，排查错复制"""
import csv, re

V7 = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv"

with open(V7, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

print("逐条检查理由与claim相关性：")
print("=" * 60)

issues = []
for r in rows:
    cid = r["claim_id"]
    claim = r["claim_text"][:100]
    reason = r["chen_reason"]
    
    # 检查理由中是否提到了claim的核心关键词
    # 提取claim中的关键术语（大写缩写、专业术语）
    claim_terms = set(re.findall(r'\b[A-Z]{2,}\b', claim))
    claim_terms |= set(re.findall(r'\b(?:IFN|RDV|LPV|RTV|MERS|SARS|COVID|ACE2|TMPRSS2|GWAS|SNP|FMO3|TMAO|MS4A|PARL|PINK1|REAP|BMI|obesity|diet|mental)\w*', claim, re.I))
    
    # 检查理由中是否包含claim_id本身（可能是错复制的标志）
    # 比如claim 502的理由里出现"490"
    other_ids = re.findall(r'\bclaim\s*(\d{2,3})\b', reason)
    for oid in other_ids:
        if oid != cid:
            issues.append(f"claim {cid}: 理由中提到了其他claim {oid}，可能错复制")
    
    # 检查理由中证据ID与evidence_ids字段一致
    reason_evids = set(re.findall(r'D\d{2}:S\d{2}', reason))
    field_evids = set(e.strip() for e in r["chen_evidence_ids"].split(";") if e.strip())
    extra_in_reason = reason_evids - field_evids
    if extra_in_reason:
        issues.append(f"claim {cid}: 理由中出现了evidence_ids字段外的证据ID: {extra_in_reason}")
    
    # 打印摘要
    label = r["chen_label"]
    evids = r["chen_evidence_ids"]
    reason_short = reason[:80].replace("\n", " ")
    print(f"[{cid}] {label} | ev={evids}")
    print(f"  claim: {claim}...")
    print(f"  reason: {reason_short}...")
    print()

print("=" * 60)
if issues:
    print(f"⚠️ 发现 {len(issues)} 个潜在问题:")
    for i in issues:
        print(f"  - {i}")
else:
    print("✅ 未发现错复制或证据ID不一致问题")
