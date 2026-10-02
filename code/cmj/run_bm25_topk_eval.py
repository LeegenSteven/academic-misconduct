"""Dependency-free BM25 evaluation on all Sarol test claims.

This evaluates only the lexical BM25 stage over the downloaded corpus. It is
not the official Pyserini+MonoT5 result and is intended as a reproducibility
smoke test.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[0] / "Citation-Integrity-main" / "Data"
CLAIMS = ROOT / "multivers-format" / "claims-test.jsonl"
CORPUS = ROOT / "multivers-format" / "corpus.jsonl"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "bm25_topk_eval_result.json"


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def load_data() -> tuple[list[dict], list[tuple[int, int, str]]]:
    with CLAIMS.open(encoding="utf-8") as handle:
        claims = [json.loads(line) for line in handle if line.strip()]
    rows: list[tuple[int, int, str]] = []
    with CORPUS.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            rows.extend(
                (int(item["doc_id"]), index, sentence)
                for index, sentence in enumerate(item.get("abstract", []))
            )
    return claims, rows


def main() -> None:
    claims, rows = load_data()
    docs = [tokens(text) for _, _, text in rows]
    lengths = [len(doc) for doc in docs]
    avgdl = sum(lengths) / len(lengths)
    postings: dict[str, list[int]] = defaultdict(list)
    term_freqs: list[dict[str, int]] = []
    for index, doc in enumerate(docs):
        tf: dict[str, int] = defaultdict(int)
        for term in doc:
            tf[term] += 1
        term_freqs.append(tf)
        for term in tf:
            postings[term].append(index)
    n_docs = len(docs)
    idf = {
        term: math.log(1.0 + (n_docs - len(indices) + 0.5) / (len(indices) + 0.5))
        for term, indices in postings.items()
    }
    k1, b = 1.5, 0.75
    topk_hits = {5: 0, 10: 0, 20: 0}
    topk_total = {5: 0, 10: 0, 20: 0}
    per_claim = []
    for claim in claims:
        query = tokens(claim["claim"])
        scores: dict[int, float] = defaultdict(float)
        for term in query:
            if term not in postings:
                continue
            for index in postings[term]:
                tf = term_freqs[index][term]
                denom = tf + k1 * (1.0 - b + b * lengths[index] / avgdl)
                scores[index] += idf[term] * tf * (k1 + 1.0) / denom
        ranked = sorted(scores, key=scores.get, reverse=True)
        gold = {
            (int(doc_id), int(sentence_index))
            for doc_id, evidence_sets in claim.get("evidence", {}).items()
            for evidence in evidence_sets
            for sentence_index in evidence.get("sentences", [])
        }
        row = {"id": claim["id"], "gold_count": len(gold)}
        for k in (5, 10, 20):
            selected = ranked[:k]
            selected_keys = {(rows[i][0], rows[i][1]) for i in selected}
            hits = len(selected_keys & gold)
            topk_hits[k] += hits
            topk_total[k] += len(gold)
            row[f"hits_at_{k}"] = hits
        per_claim.append(row)
    result = {
        "status": "completed",
        "official": False,
        "note": "Lexical BM25 over all corpus sentences; no Pyserini or MonoT5.",
        "claims": len(claims),
        "corpus_sentences": len(rows),
        "recall_at_5": topk_hits[5] / topk_total[5],
        "recall_at_10": topk_hits[10] / topk_total[10],
        "recall_at_20": topk_hits[20] / topk_total[20],
        "gold_evidence_total": topk_total[20],
        "hit_totals": {str(k): topk_hits[k] for k in (5, 10, 20)},
        "per_claim": per_claim,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_claim"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
