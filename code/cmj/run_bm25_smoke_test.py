"""Small, dependency-free BM25 smoke test for the downloaded Sarol data.

This is a data-path check, not the paper's official Pyserini run.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[0] / "Citation-Integrity-main" / "Data"
CLAIMS = ROOT / "multivers-format" / "claims-test.jsonl"
CORPUS = ROOT / "multivers-format" / "corpus.jsonl"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "bm25_smoke_test_result.json"


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def load_first_claim() -> dict:
    with CLAIMS.open(encoding="utf-8") as handle:
        return json.loads(next(line for line in handle if line.strip()))


def load_corpus() -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    with CORPUS.open(encoding="utf-8") as handle:
        for row in handle:
            item = json.loads(row)
            for sentence_index, sentence in enumerate(item.get("abstract", [])):
                rows.append((int(item["doc_id"]), sentence_index, sentence))
    return rows


def bm25(query: list[str], documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    n = len(documents)
    avgdl = sum(len(doc) for doc in documents) / max(n, 1)
    doc_freq: dict[str, int] = {}
    for doc in documents:
        for term in set(doc):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    scores: list[float] = []
    for doc in documents:
        tf: dict[str, int] = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in query:
            if term not in tf:
                continue
            df = doc_freq.get(term, 0)
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            denom = tf[term] + k1 * (1.0 - b + b * len(doc) / max(avgdl, 1.0))
            score += idf * tf[term] * (k1 + 1.0) / denom
        scores.append(score)
    return scores


def main() -> None:
    claim = load_first_claim()
    rows = load_corpus()
    docs = [tokens(text) for _, _, text in rows]
    scores = bm25(tokens(claim["claim"]), docs)
    ranked = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)[:5]

    gold = {
        (int(doc_id), int(sentence_index))
        for doc_id, evidence_sets in claim.get("evidence", {}).items()
        for evidence in evidence_sets
        for sentence_index in evidence.get("sentences", [])
    }
    top = []
    for rank, index in enumerate(ranked, start=1):
        doc_id, sentence_index, text = rows[index]
        top.append(
            {
                "rank": rank,
                "doc_id": doc_id,
                "sentence_index": sentence_index,
                "score": round(scores[index], 6),
                "is_gold": (doc_id, sentence_index) in gold,
                "text": text,
            }
        )
    result = {
        "status": "completed",
        "official": False,
        "note": "Dependency-free smoke test; not Pyserini and not MonoT5.",
        "claim_id": claim["id"],
        "claim": claim["claim"],
        "corpus_sentence_count": len(rows),
        "gold_evidence_count": len(gold),
        "top5": top,
        "gold_hit_count_top5": sum(item["is_gold"] for item in top),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
