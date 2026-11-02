# -*- coding: utf-8 -*-
import csv

with open(r'C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\陈明进_R2EXP25独立语义标注_v1_20261022.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f'总行数: {len(rows)}')
print(f'列数: {len(reader.fieldnames)}')
print()
for r in rows:
    label = r['label'] if r['label'] else '待确认'
    print(f"{r['sample_id']:18s} | {label:12s} | {r['review_status']:8s} | {r['scope_status']}")

print()
missing = []
for r in rows:
    if not r['cited_clause_text']:
        missing.append(f"{r['sample_id']}: cited_clause_text空")
    if not r['reason']:
        missing.append(f"{r['sample_id']}: reason空")
    if not r['evidence_locator']:
        missing.append(f"{r['sample_id']}: evidence_locator空")
if missing:
    print('缺失字段:')
    for m in missing:
        print(f'  {m}')
else:
    print('所有必填字段已填写')
