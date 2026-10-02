# -*- coding: utf-8 -*-
"""
任务2b：30 条样本 MonoT5 重排前后首位命中率对比
================================================
固定同一候选集（按被引文献分组 BM25 top-10）：
  - 重排前：BM25 原始分数排序的 rank1 是否命中 gold
  - 重排后：MonoT5 true-logprob 排序的 rank1 是否命中 gold
输出对比结果 json + 控制台汇总。
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
TEST_JSONL = WORK / "converted-three-class" / "claims-test.jsonl"
CORPUS = WORK / "Citation-Integrity-main" / "Data" / "multivers-format" / "corpus.jsonl"
MONOT5_30 = OUTPUTS / "monot5_30_eval_result.json"


def toks(s):
    return re.findall(r"[A-Za-z0-9]+", s.lower())


def bm25_scores(q, docs):
    n = len(docs)
    avg = sum(map(len, docs)) / max(n, 1)
    dfs = Counter(t for d in docs for t in set(d))
    out = []
    for d in docs:
        tf = Counter(d)
        z = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (n - dfs[t] + 0.5) / (dfs[t] + 0.5))
            z += idf * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * len(d) / max(avg, 1)))
        out.append(z)
    return out


def main():
    claims = {int(json.loads(x)["id"]): json.loads(x)
              for x in open(TEST_JSONL, encoding="utf-8") if x.strip()}
    corpus = {}
    for line in open(CORPUS, encoding="utf-8"):
        x = json.loads(line)
        corpus[int(x["doc_id"])] = x.get("abstract", [])
    monot5 = json.load(open(MONOT5_30, encoding="utf-8"))["results"]

    rows = []
    for item in monot5:
        cid = int(item["claim_id"])
        c = claims.get(cid)
        if c is None:
            continue
        gold = {(int(d), int(s))
                for d, es in c.get("evidence", {}).items() for e in es for s in e.get("sentences", [])}
        cand = [(int(d), i, s) for d in c["cited_doc_ids"]
                for i, s in enumerate(corpus.get(int(d), []))]
        lex = bm25_scores(toks(c["claim"]), [toks(x[2]) for x in cand])
        order = sorted(range(len(cand)), key=lambda i: lex[i], reverse=True)[:10]
        bm25_ranked = sorted(range(len(order)), key=lambda j: lex[order[j]], reverse=True)
        bm25_first = cand[order[bm25_ranked[0]]]
        bm25_hit = (bm25_first[0], bm25_first[1]) in gold

        mt5_top = item.get("top10", [])
        mt5_first = mt5_top[0] if mt5_top else None
        mt5_hit = bool(mt5_first and mt5_first.get("is_gold"))

        rows.append({
            "claim_id": cid,
            "bm25_candidate_count": len(cand),
            "bm25_rank1": {"doc_id": bm25_first[0], "sentence_index": bm25_first[1], "is_gold": bm25_hit},
            "monot5_rank1": {"doc_id": mt5_first["doc_id"] if mt5_first else None,
                             "sentence_index": mt5_first["sentence_index"] if mt5_first else None,
                             "is_gold": mt5_hit},
        })

    n = len(rows)
    b_hits = sum(1 for r in rows if r["bm25_rank1"]["is_gold"])
    m_hits = sum(1 for r in rows if r["monot5_rank1"]["is_gold"])
    both = sum(1 for r in rows if r["bm25_rank1"]["is_gold"] and r["monot5_rank1"]["is_gold"])
    only_b = sum(1 for r in rows if r["bm25_rank1"]["is_gold"] and not r["monot5_rank1"]["is_gold"])
    only_m = sum(1 for r in rows if not r["bm25_rank1"]["is_gold"] and r["monot5_rank1"]["is_gold"])

    out = {
        "status": "completed",
        "task": "30条样本 MonoT5 重排前后首位命中率对比",
        "candidate_set": "按被引文献分组 BM25 top-10（固定相同候选集）",
        "claims": n,
        "bm25_rank1_hits": b_hits,
        "bm25_rank1_rate": round(b_hits / n, 4),
        "monot5_rank1_hits": m_hits,
        "monot5_rank1_rate": round(m_hits / n, 4),
        "both_hit": both, "only_bm25": only_b, "only_monot5": only_m,
        "results": rows,
    }
    out_path = OUTPUTS / "rerank_before_after_30_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"样本数: {n}")
    print(f"重排前 BM25 rank1 命中: {b_hits}/{n} = {b_hits/n:.4f}")
    print(f"重排后 MonoT5 rank1 命中: {m_hits}/{n} = {m_hits/n:.4f}")
    print(f"同时命中: {both} | 仅BM25命中: {only_b} | 仅MonoT5命中: {only_m}")
    print(f"结果已存: {out_path}")


if __name__ == "__main__":
    main()
