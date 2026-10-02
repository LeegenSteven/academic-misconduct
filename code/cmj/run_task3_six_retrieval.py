# -*- coding: utf-8 -*-
"""
任务3a：Dev 316 条六档检索对照
- 被引文献内固定 BM25 前 50 候选句（不足取全部）
- 比较原始 BM25 排序 vs MonoT5 重排后 top-5/10/20 六档
- 区分句级（(doc,句子)命中）与块级（doc 命中）Recall，报告重排耗时
Recall 在 255 条有证据子集上计算（无证据样本无金标准句）。
"""
import json, math, re, time
from collections import Counter
from pathlib import Path
import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer

ROOT = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\Citation-Integrity-main\Data\multivers-format")
OUT = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs\task3_six_retrieval_result_2026-09-16.json")
MODEL = str(Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\hf_cache\hub\models--castorini--monot5-base-med-msmarco\snapshots\7a4324f2785ab5f1dea00e7a39d6f81f3e2d273f"))

def toks(s): return re.findall(r"[A-Za-z0-9]+", s.lower())

def bm25(q, docs):
    n = len(docs); avg = sum(map(len, docs)) / max(n, 1); dfs = Counter(t for d in docs for t in set(d)); out = []
    for d in docs:
        tf = Counter(d); z = 0.0
        for t in q:
            if t not in tf: continue
            idf = math.log(1 + (n - dfs[t] + 0.5) / (dfs[t] + 0.5))
            z += idf * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * len(d) / max(avg, 1)))
        out.append(z)
    return out

def main():
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    print("[1/4] 加载 Dev + corpus...", flush=True)
    claims = [json.loads(x) for x in (ROOT / "claims-dev.jsonl").open(encoding="utf-8") if x.strip()]
    corpus = {}
    for line in (ROOT / "corpus.jsonl").open(encoding="utf-8"):
        x = json.loads(line); corpus[int(x["doc_id"])] = x.get("abstract", [])
    if limit:
        claims = claims[:limit]

    # 有证据子集
    ev_claims = [c for c in claims if c.get("evidence")]
    print(f"      Dev {len(claims)} 条，有证据 {len(ev_claims)} 条（Recall 在此计算）", flush=True)

    print("[2/4] 加载 MonoT5...", flush=True)
    tokenizer = T5Tokenizer.from_pretrained(MODEL, use_fast=False, local_files_only=True)
    model = T5ForConditionalGeneration.from_pretrained(MODEL, local_files_only=True); model.eval()
    true_id = tokenizer("true", add_special_tokens=False).input_ids[0]
    false_id = tokenizer("false", add_special_tokens=False).input_ids[0]

    print("[3/4] BM25 top-50 + MonoT5 重排...", flush=True)
    t_rerank = 0.0
    t_wall0 = time.time()
    rows = []
    for ci, claim in enumerate(ev_claims, 1):
        gold_sent = {(int(d), int(s)) for d, es in claim.get("evidence", {}).items() for e in es for s in e.get("sentences", [])}
        gold_docs = {int(d) for d in claim.get("evidence", {})}
        cand = [(int(d), i, s) for d in claim["cited_doc_ids"] for i, s in enumerate(corpus.get(int(d), []))]
        row = {"claim_id": claim["id"], "n_gold_sent": len(gold_sent), "n_gold_docs": len(gold_docs),
               "n_cand": len(cand), "bm25_rank": [], "monot5_rank": []}
        if cand:
            lex = bm25(toks(claim["claim"]), [toks(x[2]) for x in cand])
            bm25_order = sorted(range(len(cand)), key=lambda i: lex[i], reverse=True)[:50]
            row["bm25_rank"] = [{"doc_id": cand[i][0], "sentence_index": cand[i][1], "is_gold_sent": (cand[i][0], cand[i][1]) in gold_sent,
                                 "is_gold_doc": cand[i][0] in gold_docs, "text": cand[i][2]} for i in bm25_order]
            # MonoT5 重排
            prompts = [f"Query: {claim['claim']} Document: {cand[i][2]} Relevant:" for i in bm25_order]
            t0 = time.time()
            scores = []
            for j in range(0, len(prompts), 16):
                batch = prompts[j:j+16]
                inp = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
                with torch.no_grad():
                    logits = model(**inp, decoder_input_ids=torch.full((len(batch), 1), model.config.decoder_start_token_id, dtype=torch.long)).logits[:, -1, :]
                lp = torch.log_softmax(logits[:, [true_id, false_id]], dim=-1)[:, 0].tolist()
                scores.extend(lp)
            t_rerank += time.time() - t0
            ranked = sorted(range(len(bm25_order)), key=lambda j: scores[j], reverse=True)
            row["monot5_rank"] = [{"doc_id": cand[bm25_order[j]][0], "sentence_index": cand[bm25_order[j]][1],
                                   "is_gold_sent": (cand[bm25_order[j]][0], cand[bm25_order[j]][1]) in gold_sent,
                                   "is_gold_doc": cand[bm25_order[j]][0] in gold_docs} for j in ranked]
        rows.append(row)
        if ci % 60 == 0 or ci == len(ev_claims):
            print(f"      {ci}/{len(ev_claims)} (墙钟 {time.time()-t_wall0:.0f}s, 重排累计 {t_rerank:.0f}s)", flush=True)

    print("[4/4] 六档 Recall 汇总...", flush=True)
    def recall(k, which):
        hit_sent = hit_doc = tot_sent = tot_doc = 0
        for r in rows:
            top = r[which][:k]
            gs, gd = r["n_gold_sent"], r["n_gold_docs"]
            hs = sum(1 for x in top if x["is_gold_sent"]); hd = sum(1 for x in top if x["is_gold_doc"])
            if gs: hit_sent += min(hs, gs); tot_sent += gs
            if gd: hit_doc += min(hd, gd); tot_doc += gd
        return {"sentence_recall": round(hit_sent / tot_sent, 4) if tot_sent else None,
                "block_recall": round(hit_doc / tot_doc, 4) if tot_doc else None,
                "gold_sent_hits": hit_sent, "gold_sent_total": tot_sent,
                "gold_doc_hits": hit_doc, "gold_doc_total": tot_doc}

    summary = {}
    for k in (5, 10, 20):
        summary[f"bm25_top{k}"] = recall(k, "bm25_rank")
        summary[f"monot5_top{k}"] = recall(k, "monot5_rank")

    out = {"task": "任务3a：Dev 六档检索对照（BM25 top50 原始 vs MonoT5 重排，5/10/20）",
           "n_claims_with_evidence": len(rows), "rerank_elapsed_seconds": round(t_rerank, 2),
           "summary": summary, "results": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 六档 Recall（255 有证据子集）===")
    for k in (5, 10, 20):
        b, m = summary[f"bm25_top{k}"], summary[f"monot5_top{k}"]
        print(f"top-{k}: BM25 句级R={b['sentence_recall']} 块级R={b['block_recall']} | MonoT5 句级R={m['sentence_recall']} 块级R={m['block_recall']}")
    print(f"MonoT5 重排耗时: {t_rerank:.1f}s")
    print("结果已存:", OUT)

if __name__ == "__main__":
    main()
