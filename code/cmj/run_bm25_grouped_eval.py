"""BM25 smoke evaluation with the paper's candidate-document restriction.

For each claim, rank sentences only inside its cited_doc_ids. This is closer
to the author's per-reference-document Lucene indexes, but still not the
official Pyserini+MonoT5 implementation.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0] / "Citation-Integrity-main" / "Data" / "multivers-format"
CLAIMS = ROOT / "claims-test.jsonl"
CORPUS = ROOT / "corpus.jsonl"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "bm25_grouped_eval_result.json"


def toks(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def score(query: list[str], docs: list[list[str]]) -> list[float]:
    n = len(docs)
    avgdl = sum(map(len, docs)) / max(n, 1)
    dfs = Counter(term for doc in docs for term in set(doc))
    out = []
    for doc in docs:
        tf = Counter(doc)
        total = 0.0
        for term in query:
            if term not in tf:
                continue
            idf = math.log(1.0 + (n - dfs[term] + 0.5) / (dfs[term] + 0.5))
            denom = tf[term] + 1.5 * (1.0 - 0.75 + 0.75 * len(doc) / max(avgdl, 1.0))
            total += idf * tf[term] * 2.5 / denom
        out.append(total)
    return out


def main() -> None:
    claims = [json.loads(line) for line in CLAIMS.open(encoding="utf-8") if line.strip()]
    corpus = {}
    for line in CORPUS.open(encoding="utf-8"):
        row = json.loads(line)
        corpus[int(row["doc_id"])] = row.get("abstract", [])
    totals = {5: 0, 10: 0, 20: 0}
    gold_total = 0
    per_claim = []
    for claim in claims:
        candidates = []
        for doc_id in claim.get("cited_doc_ids", []):
            for index, text in enumerate(corpus.get(int(doc_id), [])):
                candidates.append((int(doc_id), index, text))
        scores = score(toks(claim["claim"]), [toks(x[2]) for x in candidates])
        ranked = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
        gold = {
            (int(doc_id), int(sent_idx))
            for doc_id, evidence_sets in claim.get("evidence", {}).items()
            for evidence in evidence_sets
            for sent_idx in evidence.get("sentences", [])
        }
        gold_total += len(gold)
        row = {"id": claim["id"], "candidate_sentences": len(candidates), "gold_count": len(gold)}
        for k in (5, 10, 20):
            keys = {(candidates[i][0], candidates[i][1]) for i in ranked[:k]}
            hit = len(keys & gold)
            totals[k] += hit
            row[f"hits_at_{k}"] = hit
        per_claim.append(row)
    result = {
        "status": "completed",
        "official": False,
        "note": "Grouped lexical BM25 over each claim's cited_doc_ids; no Pyserini or MonoT5.",
        "claims": len(claims),
        "corpus_documents": len(corpus),
        "gold_evidence_total": gold_total,
        "hit_totals": {str(k): totals[k] for k in (5, 10, 20)},
        "recall_at_5": totals[5] / gold_total,
        "recall_at_10": totals[10] / gold_total,
        "recall_at_20": totals[20] / gold_total,
        "per_claim": per_claim,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_claim"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
