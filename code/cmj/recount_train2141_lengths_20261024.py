# -*- coding: utf-8 -*-
"""Sarol Train 2141 长度/样本数复算（官方 tokenizer + data_contract 编码逻辑）。

对齐点：
- 输入：results/route1_qwen38_v2/2026-10-15/sarol/train.inputs.jsonl + train.gold.jsonl
- 编码：data_contract.encode_assistant_record（apply_chat_template + 字符偏移 mask + EOS 监督）
- 验收口径：总条数 2141；max_length=4096 下超长 3 条、最大 4924；
  max_length=5120 下无超长（未截断）；监督 token 合计 20042；
  标签分布 ACCURATE 1368 / NOT_ACCURATE 630 / IRRELEVANT 143。
本脚本只做统计，不加载模型、不训练、不写历史 checkpoint。
"""
import json
import os
import sys

sys.path.insert(0, r"C:\Users\Administrator\Documents\academic-misconduct\code")
from shared.route1_qwen38.data_contract import encode_assistant_record, load_gold, load_records

REPO = r"C:\Users\Administrator\Documents\academic-misconduct"
MODEL_DIR = r"C:\Users\Administrator\Documents\models\Qwen3.8-27B"
INPUTS = os.path.join(REPO, "results", "route1_qwen38_v2", "2026-10-15", "sarol", "train.inputs.jsonl")
GOLD = os.path.join(REPO, "results", "route1_qwen38_v2", "2026-10-15", "sarol", "train.gold.jsonl")

from transformers import AutoTokenizer

def main():
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_DIR, trust_remote_code=True, local_files_only=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    labels = load_gold(GOLD, split="train")
    records = load_records(INPUTS, labels)

    lengths = []
    supervised_total = 0
    over4096 = []
    over5120 = []
    label_dist = {"ACCURATE": 0, "NOT_ACCURATE": 0, "IRRELEVANT": 0}
    eos_counts = []
    failures = []

    for rec in records:
        try:
            enc = encode_assistant_record(rec, tokenizer, max_length=5120)
        except ValueError as exc:
            failures.append((rec["claim_id"], str(exc)))
            continue
        n = len(enc["input_ids"])
        lengths.append(n)
        sup = sum(1 for t in enc["labels"] if t != -100)
        supervised_total += sup
        eos_counts.append(sum(1 for t in enc["labels"] if t != -100 and t == tokenizer.eos_token_id))
        label_dist[rec["label"]] += 1
        if n > 4096:
            over4096.append((rec["claim_id"], n, rec["label"]))
        if n > 5120:
            over5120.append((rec["claim_id"], n, rec["label"]))

    # 与 4096 口径对齐：上报超长的判定（data_contract 在 max_length=4096 时抛错）
    over4096_at_4096 = [(cid, n, lab) for cid, n, lab in over4096 if n > 4096]

    print("=== 样本数 ===")
    print("total_records:", len(records))
    print("label_distribution:", label_dist)
    print("encoding_failures:", failures)

    print("\n=== 长度统计 (token, 官方tokenizer+chat_template) ===")
    print("min:", min(lengths) if lengths else None)
    print("max:", max(lengths) if lengths else None)
    print("mean:", round(sum(lengths) / len(lengths), 2) if lengths else None)
    print("median:", sorted(lengths)[len(lengths) // 2] if lengths else None)

    print("\n=== 超 4096（max_length=4096 将报超长）===")
    over4096.sort(key=lambda x: -x[1])
    print("count:", len(over4096_at_4096))
    for cid, n, lab in over4096_at_4096:
        print("  claim_id=%s len=%d label=%s" % (cid, n, lab))

    print("\n=== 超 5120（max_length=5120 将报超长）===")
    print("count:", len(over5120))
    for cid, n, lab in over5120:
        print("  claim_id=%s len=%d label=%s" % (cid, n, lab))

    print("\n=== 监督 token ===")
    print("supervised_total:", supervised_total)
    print("samples_with_eos_supervised:", sum(1 for c in eos_counts if c > 0), "/", len(eos_counts))
    print("total_eos_supervised:", sum(eos_counts))

    print("\n=== 结论 ===")
    ok_total = len(records) == 2141
    ok_4096 = len(over4096_at_4096) == 3 and max((x[1] for x in over4096_at_4096), default=0) == 4924
    ok_5120 = len(over5120) == 0
    ok_sup = supervised_total == 20042
    ok_label = label_dist == {"ACCURATE": 1368, "NOT_ACCURATE": 630, "IRRELEVANT": 143}
    ok_fail = not failures
    print("records==2141:", ok_total)
    print("over4096==3 & max==4924:", ok_4096)
    print("over5120==0 (5120 未截断):", ok_5120)
    print("supervised_total==20042:", ok_sup)
    print("label_dist match:", ok_label)
    print("no encode failure:", ok_fail)
    print("ALL_PASS:", ok_total and ok_4096 and ok_5120 and ok_sup and ok_label and ok_fail)

    out = {
        "total_records": len(records),
        "label_distribution": label_dist,
        "min_length": min(lengths) if lengths else None,
        "max_length": max(lengths) if lengths else None,
        "mean_length": round(sum(lengths) / len(lengths), 2) if lengths else None,
        "median_length": sorted(lengths)[len(lengths) // 2] if lengths else None,
        "over_4096_count": len(over4096_at_4096),
        "over_4096_records": [{"claim_id": c, "length": n, "label": l} for c, n, l in over4096_at_4096],
        "over_5120_count": len(over5120),
        "supervised_token_total": supervised_total,
        "samples_with_eos_supervised": sum(1 for c in eos_counts if c > 0),
        "total_eos_supervised": sum(eos_counts),
        "encoding_failures": failures,
        "tokenizer": "Qwen3.8-27B official (trust_remote_code=True, local_files_only)",
        "input_file": INPUTS,
        "gold_file": GOLD,
        "check_date": "2026-10-24",
        "all_pass": ok_total and ok_4096 and ok_5120 and ok_sup and ok_label and ok_fail,
    }
    out_path = os.path.join(REPO, "results", "route1_qwen38_v2", "2026-10-15", "sarol", "sarol_train2141_length_recount_20261024.json")
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print("\nwritten:", out_path)


if __name__ == "__main__":
    main()
