"""Single-claim MonoT5 reranking smoke test using the downloaded checkpoint."""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer


ROOT = Path(__file__).resolve().parents[0] / "Citation-Integrity-main" / "Data" / "multivers-format"
CLAIMS = ROOT / "claims-test.jsonl"
CORPUS = ROOT / "corpus.jsonl"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "monot5_smoke_test_result.json"
MODEL = "castorini/monot5-base-med-msmarco"


def toks(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def bm25(query: list[str], docs: list[list[str]]) -> list[float]:
    n = len(docs)
    avgdl = sum(map(len, docs)) / max(n, 1)
    dfs = Counter(term for doc in docs for term in set(doc))
    scores = []
    for doc in docs:
        tf = Counter(doc)
        score = 0.0
        for term in query:
            if term not in tf:
                continue
            idf = math.log(1.0 + (n - dfs[term] + 0.5) / (dfs[term] + 0.5))
            denom = tf[term] + 1.5 * (1.0 - 0.75 + 0.75 * len(doc) / max(avgdl, 1.0))
            score += idf * tf[term] * 2.5 / denom
        scores.append(score)
    return scores


def main() -> None:
    start = time.time()
    claim = next(json.loads(line) for line in CLAIMS.open(encoding="utf-8") if line.strip())
    corpus = {}
    for line in CORPUS.open(encoding="utf-8"):
        row = json.loads(line)
        corpus[int(row["doc_id"])] = row.get("abstract", [])
    candidates = [
        (int(doc_id), index, text)
        for doc_id in claim["cited_doc_ids"]
        for index, text in enumerate(corpus.get(int(doc_id), []))
    ]
    lexical = bm25(toks(claim["claim"]), [toks(x[2]) for x in candidates])
    bm25_order = sorted(range(len(candidates)), key=lambda i: lexical[i], reverse=True)[:10]

    tokenizer = T5Tokenizer.from_pretrained(MODEL, use_fast=False)
    model = T5ForConditionalGeneration.from_pretrained(MODEL)
    model.eval()
    true_id = tokenizer("true", add_special_tokens=False).input_ids[0]
    false_id = tokenizer("false", add_special_tokens=False).input_ids[0]
    rows = []
    for rank, index in enumerate(bm25_order, start=1):
        doc_id, sent_idx, text = candidates[index]
        prompt = f"Query: {claim['claim']} Document: {text} Relevant:"
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = model(**inputs, decoder_input_ids=torch.tensor([[model.config.decoder_start_token_id]])).logits[:, -1, :]
        pair = torch.log_softmax(logits[:, [true_id, false_id]], dim=-1)[0]
        rows.append({
            "bm25_rank": rank,
            "doc_id": doc_id,
            "sentence_index": sent_idx,
            "monot5_true_logprob": float(pair[0]),
            "monot5_false_logprob": float(pair[1]),
            "is_gold": any(
                doc_id == int(gid) and sent_idx in [int(x) for ev in evs for x in ev.get("sentences", [])]
                for gid, evs in claim.get("evidence", {}).items()
            ),
            "text": text,
        })
    rows.sort(key=lambda x: x["monot5_true_logprob"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["monot5_rank"] = i
    result = {
        "status": "completed",
        "official": False,
        "note": "Real MonoT5 checkpoint on one claim; candidate pool is grouped BM25 top-10, not the full paper evaluation.",
        "model": MODEL,
        "device": "cpu",
        "claim_id": claim["id"],
        "claim": claim["claim"],
        "candidate_pool_size": len(candidates),
        "bm25_pool_size": len(bm25_order),
        "monot5_rank1_is_gold": rows[0]["is_gold"] if rows else False,
        "elapsed_seconds": round(time.time() - start, 2),
        "reranked": rows,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "reranked"}, ensure_ascii=False, indent=2))
    for row in rows:
        print(row["monot5_rank"], row["doc_id"], row["sentence_index"], row["is_gold"], round(row["monot5_true_logprob"], 4))


if __name__ == "__main__":
    main()
