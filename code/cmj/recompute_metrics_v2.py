# -*- coding: utf-8 -*-
"""任务1-重算：按 v2 新 gold 重算 Dev 两组（A金标准输入/B BM25输入）指标
方案A：预测 NEI 对齐 gold IRRELEVANT（三分类）
方案B：gold IRRELEVANT 单独统计，准确率仅在 ACCURATE/NOT_ACCURATE 子集计算
"""
import json
from collections import Counter
from itertools import product

RES = r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs\multivers_dev_contrast_result.json"
V2 = r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\converted-three-class-v2\claims-dev.jsonl"

r = json.load(open(RES, encoding="utf-8"))
v2 = {str(c["id"]): c for c in (json.loads(l) for l in open(V2, encoding="utf-8") if l.strip())}

# 对齐：result.results 的 claim_id -> v2 gold
rows = []
for x in r["results"]:
    g = v2[str(x["claim_id"])]["gold"]
    rows.append({"id": x["claim_id"], "gold_new": g, "gold_old": x["gold"],
                 "pa": x["pred_gold_input"], "pb": x["pred_bm25_input"]})
assert len(rows) == 316

# 新旧 gold 变化
old_cnt = Counter(x["gold_old"] for x in rows)
new_cnt = Counter(x["gold_new"] for x in rows)
changed = Counter((x["gold_old"], x["gold_new"]) for x in rows if x["gold_old"] != x["gold_new"])
print("旧 gold 分布:", dict(old_cnt))
print("新 gold 分布:", dict(new_cnt))
print("新旧变化:", dict(changed))

def metrics(pred_key, scheme):
    """scheme: A=NEI对齐IRRELEVANT; B=IRRELEVANT单独"""
    classes = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]
    # 混淆矩阵 gold -> pred
    cm = {g: Counter() for g in classes}
    for x in rows:
        g, p = x["gold_new"], x[pred_key]
        if scheme == "A":
            if p == "NEI":
                p = "IRRELEVANT"
            cm[g][p] += 1
        else:  # B
            cm[g][p] += 1  # pred 保持原样(NEI独立)
    if scheme == "A":
        total = len(rows)
        correct = sum(cm[g][g] for g in classes)
        acc = correct / total
        cls_metrics = {}
        for g in classes:
            tp = cm[g][g]
            fp = sum(cm[g2][g] for g2 in classes if g2 != g)
            fn = sum(cm[g][p2] for p2 in classes if p2 != g)
            p_ = tp / (tp + fp) if tp + fp else 0
            r_ = tp / (tp + fn) if tp + fn else 0
            f1 = 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
            cls_metrics[g] = {"P": round(p_, 4), "R": round(r_, 4), "F1": round(f1, 4), "n": tp + fn}
        macro = sum(m["F1"] for m in cls_metrics.values()) / len(classes)
        return {"accuracy": round(acc, 4), "correct": correct, "total": total,
                "per_class": cls_metrics, "macro_f1": round(macro, 4)}
    else:
        # 方案B：gold IRRELEVANT 单独统计
        sub = [x for x in rows if x["gold_new"] != "IRRELEVANT"]
        n_irr = len(rows) - len(sub)
        acc = sum(1 for x in sub if x[pred_key] == x["gold_new"]) / len(sub)
        cls_metrics = {}
        for g in ("ACCURATE", "NOT_ACCURATE"):
            tp = sum(1 for x in sub if x["gold_new"] == g and x[pred_key] == g)
            fp = sum(1 for x in sub if x["gold_new"] != g and x[pred_key] == g)
            fn = sum(1 for x in sub if x["gold_new"] == g and x[pred_key] != g)
            p_ = tp / (tp + fp) if tp + fp else 0
            r_ = tp / (tp + fn) if tp + fn else 0
            f1 = 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
            cls_metrics[g] = {"P": round(p_, 4), "R": round(r_, 4), "F1": round(f1, 4), "n": tp + fn}
        macro = sum(m["F1"] for m in cls_metrics.values()) / 2
        # IRRELEVANT 24 条上预测分布
        irr_pred = Counter(x[pred_key] for x in rows if x["gold_new"] == "IRRELEVANT")
        return {"accuracy_sub": round(acc, 4), "sub_total": len(sub), "n_irrelevant": n_irr,
                "irrelevant_pred_dist": dict(irr_pred),
                "per_class": cls_metrics, "macro_f1": round(macro, 4)}

out = {"new_gold_dist": dict(new_cnt), "old_gold_dist": dict(old_cnt),
       "gold_change": {f"{a}->{b}": n for (a, b), n in changed.items()}}
for pk, name in (("pa", "A金标准输入"), ("pb", "B_BM25输入")):
    for sch, sname in (("A", "方案A(NEI对齐IRRELEVANT)"), ("B", "方案B(IRRELEVANT单独)")):
        m = metrics(pk, sch)
        out[f"{name}_{sname}"] = m
        print(f"\n=== {name} / {sname} ===")
        print(json.dumps(m, ensure_ascii=False, indent=1))

out_path = r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs\dev_metrics_v2_2026-09-16.json"
json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n结果已存:", out_path)
