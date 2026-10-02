# -*- coding: utf-8 -*-
"""评估 MultiVerS 官方权重预测 vs Sarol gold（claim 级三分类聚合）"""
import json, sys
from pathlib import Path
from collections import Counter

WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
CLAIMS_TEST = WORK / "converted-three-class" / "claims-test.jsonl"
DEFAULT_RESULT = OUTPUTS / "multivers_official_30_result.json"

FINE_TO_3 = {
    "ACCURATE": "ACCURATE", "INDIRECT": "ACCURATE", "INDIRECT_NOT_REVIEW": "ACCURATE",
    "CONTRADICT": "NOT_ACCURATE", "NOT_SUBSTANTIATE": "NOT_ACCURATE",
    "MISQUOTE": "NOT_ACCURATE", "OVERSIMPLIFY": "NOT_ACCURATE",
    "ETIQUETTE": "NOT_ACCURATE", "IRRELEVANT": "IRRELEVANT",
    # converted-three-class 数据里已是三分类字符串，原样保留
    "NOT_ACCURATE": "NOT_ACCURATE",
}


def claim_gold(path):
    """每条 claim 的 gold 三分类：证据含 NOT_ACCURATE 类→NOT_ACCURATE；全 ACCURATE→ACCURATE；无证据→NEI(IRRELEVANT)"""
    gold = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            cid = int(d["id"])
            labels = [FINE_TO_3.get(ev["label"], "UNK")
                      for evs in d.get("evidence", {}).values() for ev in evs]
            if not labels:
                gold[cid] = "NEI"
            elif any(l == "NOT_ACCURATE" for l in labels):
                gold[cid] = "NOT_ACCURATE"
            else:
                gold[cid] = "ACCURATE"
    return gold


def main():
    result_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESULT
    with open(result_path, encoding="utf-8") as f:
        res = json.load(f)
    gold = claim_gold(CLAIMS_TEST)

    rows = []
    for r in res["results"]:
        cid = r["claim_id"]
        rows.append((cid, gold.get(cid, "?"), r["predicted_label"], r["label_probs"]))

    n = len(rows)
    correct = sum(1 for _, g, p, _ in rows if g == p)
    print(f"评估条数: {n}（其中 gold 为 NEI/无证据映射）")
    print(f"总体准确率: {correct}/{n} = {correct/n:.3f}")
    print("\n预测分布:", dict(Counter(p for _, _, p, _ in rows)))
    print("gold 分布:", dict(Counter(g for _, g, _, _ in rows)))
    print("\n混淆矩阵（行=gold，列=预测）:")
    labels = ["ACCURATE", "NOT_ACCURATE", "NEI"]
    print("gold\\pred | " + " | ".join(f"{l:>12}" for l in labels))
    for g in labels:
        line = [sum(1 for _, gg, pp, _ in rows if gg == g and pp == p) for p in labels]
        print(f"{g:>10} | " + " | ".join(f"{v:>12}" for v in line))
    if n <= 30:
        print("\n逐条明细（仅列出预测≠gold）:")
        for cid, g, p, probs in rows:
            mark = "✅" if g == p else "❌"
            print(f"  {mark} claim {cid}: gold={g} pred={p} probs={probs}")


if __name__ == "__main__":
    main()
