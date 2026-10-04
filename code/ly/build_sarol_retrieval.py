"""Build reproducible Sarol retrieval inputs from ``sarol-quality-v1``.

The previous version recovered labels by matching the old ``annotations.zip``
files in order. That is unsafe after the label repair. This version reads the
repaired claims directly, uses their explicit ``gold`` field, and writes
grouped lexical BM25 sentence candidates. The default Dev report is BM25
top-10, matching the current evaluation convention.

This script reports retrieval coverage only. It does not create model
predictions or claim-level precision/recall/F1; use a matching prediction file
with ``evaluate_sarol_transfer.py`` for those metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path


LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")
LEGACY_TO_PROJECT = {
    "ACCURATE": "ACCURATE",
    "INDIRECT": "ACCURATE",
    "INDIRECT_NOT_REVIEW": "ACCURATE",
    "CONTRADICT": "NOT_ACCURATE",
    "NOT_SUBSTANTIATE": "NOT_ACCURATE",
    "MISQUOTE": "NOT_ACCURATE",
    "OVERSIMPLIFY": "NOT_ACCURATE",
    "ETIQUETTE": "NOT_ACCURATE",
    "IRRELEVANT": "IRRELEVANT",
    "NEI": "IRRELEVANT",
}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def tokens(text: str) -> list[str]:
    """Use the same ASCII lexical tokenization as the existing BM25 scripts."""

    return re.findall(r"[A-Za-z0-9]+", text.lower())


def bm25_scores(
    query: list[str],
    documents: list[list[str]],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Return grouped BM25 scores for a claim's candidate sentences."""

    if not documents:
        return []
    average_length = sum(len(document) for document in documents) / len(documents)
    document_frequency = Counter(term for document in documents for term in set(document))
    scores: list[float] = []
    for document in documents:
        term_frequency = Counter(document)
        score = 0.0
        for term in query:
            frequency = term_frequency.get(term, 0)
            if not frequency:
                continue
            idf = math.log(
                1.0
                + (len(documents) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + k1 * (
                1.0 - b + b * len(document) / max(average_length, 1.0)
            )
            score += idf * frequency * (k1 + 1.0) / denominator
        scores.append(score)
    return scores


def project_label(raw_label: str | None) -> str | None:
    if raw_label is None:
        return None
    if raw_label in LABELS:
        return raw_label
    try:
        return LEGACY_TO_PROJECT[raw_label]
    except KeyError as exc:
        raise ValueError(f"Unsupported gold label: {raw_label!r}") from exc


def sentence_candidates(claim: dict, corpus: dict[int, dict]) -> list[tuple[int, int, str]]:
    candidates: list[tuple[int, int, str]] = []
    for raw_doc_id in claim.get("cited_doc_ids", []):
        doc_id = int(raw_doc_id)
        document = corpus.get(doc_id)
        if document is None:
            continue
        for sentence_index, sentence in enumerate(document.get("abstract", [])):
            candidates.append((doc_id, sentence_index, str(sentence)))
    return candidates


def gold_sentence_keys(claim: dict) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    for raw_doc_id, evidence_sets in claim.get("evidence", {}).items():
        for evidence in evidence_sets:
            for sentence_index in evidence.get("sentences", []):
                keys.add((int(raw_doc_id), int(sentence_index)))
    return keys


def build_mapping(claims: list[dict], split: str) -> list[dict]:
    rows: list[dict] = []
    for claim in claims:
        gold = project_label(claim.get("gold"))
        evidence_keys = gold_sentence_keys(claim)
        evidence_docs = {doc_id for doc_id, _ in evidence_keys}
        rows.append(
            {
                "claim_id": str(claim["id"]),
                "sample_id": claim.get("sample_id", ""),
                "split": split,
                "raw_label": claim.get("gold"),
                "project_label": gold,
                "evidence_missing": bool(claim.get("evidence_missing", not evidence_keys)),
                "gold_evidence_doc_count": len(evidence_docs),
                "gold_evidence_sentence_count": len(evidence_keys),
            }
        )
    return rows


def write_mapping(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def portable_path(path: Path, root: Path) -> str:
    """Write repository-relative paths when possible, never local usernames."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def build_candidate_row(claim: dict, ranked: list[tuple[int, int, str, float]]) -> dict:
    return {
        "id": str(claim["id"]),
        "sample_id": claim.get("sample_id", ""),
        "claim": claim["claim"],
        "doc_ids": [doc_id for doc_id, _, _, _ in ranked],
        "evidence_sentences": [
            {
                "doc_id": doc_id,
                "sentence_index": sentence_index,
                "text": text,
                "bm25_score": round(score, 8),
            }
            for doc_id, sentence_index, text, score in ranked
        ],
    }


def retrieval_summary(
    claims: list[dict],
    rows: list[dict],
    corpus_blocks: int,
    top_k: int,
    k1: float,
    b: float,
) -> dict:
    gold_sentence_total = 0
    hit_sentence_total = 0
    gold_doc_total = 0
    hit_doc_total = 0
    claims_with_gold = 0
    claims_with_sentence_hit = 0
    claims_with_doc_hit = 0
    empty_candidates = 0

    for claim, row in zip(claims, rows):
        gold_keys = gold_sentence_keys(claim)
        gold_docs = {doc_id for doc_id, _ in gold_keys}
        top_keys = {
            (item["doc_id"], item["sentence_index"])
            for item in row["evidence_sentences"]
        }
        top_docs = {item["doc_id"] for item in row["evidence_sentences"]}
        gold_sentence_total += len(gold_keys)
        hit_sentence_total += len(gold_keys & top_keys)
        gold_doc_total += len(gold_docs)
        hit_doc_total += len(gold_docs & top_docs)
        claims_with_gold += int(bool(gold_keys))
        claims_with_sentence_hit += int(bool(gold_keys & top_keys))
        claims_with_doc_hit += int(bool(gold_docs & top_docs))
        empty_candidates += int(not row["evidence_sentences"])

    return {
        "top_k": top_k,
        "claims": len(claims),
        "corpus_blocks": corpus_blocks,
        "retriever": "grouped lexical BM25",
        "candidate_scope": "all abstract sentences from each claim's cited_doc_ids",
        "k1": k1,
        "b": b,
        "gold_sentence_total": gold_sentence_total,
        "retrieved_gold_sentence_total": hit_sentence_total,
        "evidence_sentence_recall": hit_sentence_total / gold_sentence_total
        if gold_sentence_total
        else 0.0,
        "gold_document_total": gold_doc_total,
        "retrieved_gold_document_total": hit_doc_total,
        "evidence_document_recall": hit_doc_total / gold_doc_total
        if gold_doc_total
        else 0.0,
        "claims_with_gold_evidence": claims_with_gold,
        "claims_with_at_least_one_sentence_hit": claims_with_sentence_hit,
        "claim_level_sentence_recall": claims_with_sentence_hit / claims_with_gold
        if claims_with_gold
        else 0.0,
        "claims_with_at_least_one_document_hit": claims_with_doc_hit,
        "claim_level_document_recall": claims_with_doc_hit / claims_with_gold
        if claims_with_gold
        else 0.0,
        "empty_candidate_claims": empty_candidates,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=root / "data" / "quality_v1" / "sarol",
        help="Directory containing claims-{split}-model.jsonl and corpus.jsonl.",
    )
    parser.add_argument("--split", choices=("train", "dev", "test"), default="dev")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "results" / "ly" / "sarol_quality_v1_dev_bm25",
    )
    parser.add_argument("--top-k", type=int, nargs="+", default=[10])
    parser.add_argument("--k1", type=float, default=1.5)
    parser.add_argument("--b", type=float, default=0.75)
    args = parser.parse_args()

    if any(k <= 0 for k in args.top_k):
        raise ValueError("Every --top-k value must be positive")
    claims_path = args.data / f"claims-{args.split}-model.jsonl"
    corpus_path = args.data / "corpus.jsonl"
    if not claims_path.exists():
        raise FileNotFoundError(claims_path)
    if not corpus_path.exists():
        raise FileNotFoundError(corpus_path)

    claims = load_jsonl(claims_path)
    corpus = {int(row["doc_id"]): row for row in load_jsonl(corpus_path)}
    if not claims:
        raise ValueError("No claims were loaded")
    if len({str(row["id"]) for row in claims}) != len(claims):
        raise ValueError("Claim IDs are not unique")

    mapping = build_mapping(claims, args.split)
    args.output.mkdir(parents=True, exist_ok=True)
    write_mapping(args.output / f"gold_mapping_{args.split}.csv", mapping)

    ranked_by_claim: dict[str, list[tuple[int, int, str, float]]] = {}
    for claim in claims:
        candidates = sentence_candidates(claim, corpus)
        scores = bm25_scores(
            tokens(claim["claim"]),
            [tokens(item[2]) for item in candidates],
            args.k1,
            args.b,
        )
        order = sorted(
            range(len(candidates)),
            key=lambda index: (-scores[index], candidates[index][0], candidates[index][1]),
        )
        ranked_by_claim[str(claim["id"])] = [
            (*candidates[index], scores[index]) for index in order
        ]

    metric_summaries: dict[str, dict] = {}
    for top_k in sorted(set(args.top_k)):
        rows: list[dict] = []
        for claim in claims:
            ranked = ranked_by_claim[str(claim["id"])][:top_k]
            rows.append(build_candidate_row(claim, ranked))
        write_jsonl(args.output / f"claims_{args.split}_bm25_top{top_k}.jsonl", rows)
        metric_summaries[str(top_k)] = retrieval_summary(
            claims, rows, len(corpus), top_k, args.k1, args.b
        )

    manifest = {
        "status": "completed",
        "data_version": "sarol-quality-v1",
        "split": args.split,
        "claims_path": portable_path(claims_path, root),
        "corpus_path": portable_path(corpus_path, root),
        "claims": len(claims),
        "corpus_blocks": len(corpus),
        "project_label_counts": dict(
            Counter(row["project_label"] for row in mapping if row["project_label"] is not None)
        ),
        "gold_null_count": sum(row["project_label"] is None for row in mapping),
        "top_k": sorted(set(args.top_k)),
        "retriever": "grouped lexical BM25",
        "candidate_scope": "all abstract sentences from each claim's cited_doc_ids",
        "gold_source": "explicit claims[*].gold; no annotations.zip recovery",
        "note": "Retrieval metrics only. Model class metrics require matching predictions and evaluate_sarol_transfer.py.",
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for top_k, summary in metric_summaries.items():
        (args.output / f"retrieval_metrics_top{top_k}.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        json.dumps(
            {"manifest": manifest, "metrics": metric_summaries},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
