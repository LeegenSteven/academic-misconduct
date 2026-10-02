from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


PROJECT_LABEL = {
    "ACCURATE": "ACCURATE",
    "INDIRECT": "ACCURATE",
    "INDIRECT_NOT_REVIEW": "ACCURATE",
    "CONTRADICT": "NOT_ACCURATE",
    "NOT_SUBSTANTIATE": "NOT_ACCURATE",
    "MISQUOTE": "NOT_ACCURATE",
    "OVERSIMPLIFY": "NOT_ACCURATE",
    "ETIQUETTE": "NOT_ACCURATE",
    "IRRELEVANT": "IRRELEVANT",
}


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"<\|(?:multi_cit|cit|other_cit)\|>", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_raw_dev_labels(annotations: Path):
    rows = []
    with zipfile.ZipFile(annotations) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.startswith("annotations/Dev/citations/") and name.endswith(".json") and "__MACOSX" not in name
        ]
        for name in names:
            row = json.loads(archive.read(name).decode("utf-8-sig"))
            group_match = re.search(r"annotations/Dev/citations/(\d+)_", name)
            if group_match is None:
                raise ValueError(f"Cannot recover cited-paper group from {name}")
            rows.append({
                "file": name,
                "group": int(group_match.group(1)),
                "label": row["label"],
                "paragraph": normalize(row["citing_paragraph"]),
                "contexts": [normalize(item["text"]) for item in row["citation_context"]],
            })
    return rows


def recover_labels(claims, raw_rows):
    """Pair claims and raw annotations by their stable order within each cited-paper group."""
    raw_by_group = defaultdict(list)
    for row in raw_rows:
        raw_by_group[row["group"]].append(row)
    claim_counts = Counter(int(claim["cited_doc_ids"][0]) // 1000 for claim in claims)
    raw_counts = Counter({group: len(rows) for group, rows in raw_by_group.items()})
    if claim_counts != raw_counts:
        raise ValueError(f"Claim/raw group counts differ: claims={claim_counts}, raw={raw_counts}")

    positions = Counter()
    result = {}
    for claim in claims:
        candidate_groups = {int(doc_id) // 1000 for doc_id in claim["cited_doc_ids"]}
        if len(candidate_groups) != 1:
            raise ValueError(f"Claim {claim['id']} spans unexpected cited-paper groups: {candidate_groups}")
        group = next(iter(candidate_groups))
        raw = raw_by_group[group][positions[group]]
        positions[group] += 1
        normalized = normalize(claim["claim"])
        context_matches = any(
            context == normalized or context in normalized or normalized in context
            for context in raw["contexts"]
        )
        if not context_matches:
            raise ValueError(f"Claim/raw order mismatch for claim {claim['id']} and {raw['file']}")
        result[claim["id"]] = (raw["label"], [raw["file"]])
    return result


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=root / "成员1反馈 Data")
    parser.add_argument("--output", type=Path, default=root / "sarol_transfer_input")
    parser.add_argument("--top-k", type=int, nargs="+", default=[5, 10, 20])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    claims = load_jsonl(args.data / "multivers-format" / "claims-dev.jsonl")
    corpus = load_jsonl(args.data / "multivers-format" / "corpus.jsonl")
    raw_rows = load_raw_dev_labels(args.data / "annotations.zip")
    labels_by_claim = recover_labels(claims, raw_rows)
    corpus_by_id = {row["doc_id"]: row for row in corpus}
    corpus_index = {row["doc_id"]: index for index, row in enumerate(corpus)}
    texts = [row.get("title", "") + " " + " ".join(row.get("abstract", [])) for row in corpus]

    vectorizer = TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=(1, 2), sublinear_tf=True)
    doc_matrix = vectorizer.fit_transform(texts)
    query_matrix = vectorizer.transform([row["claim"] for row in claims])

    mappings = []
    rankings = {}
    for row_index, claim in enumerate(claims):
        fine_label, annotation_files = labels_by_claim[claim["id"]]
        candidates = claim["cited_doc_ids"]
        indices = [corpus_index[doc_id] for doc_id in candidates]
        scores = (query_matrix[row_index] @ doc_matrix[indices].T).toarray()[0]
        order = np.argsort(scores)[::-1]
        ranked_docs = [candidates[i] for i in order]
        rankings[claim["id"]] = ranked_docs
        mappings.append({
            "claim_id": claim["id"],
            "fine_label": fine_label,
            "project_label": PROJECT_LABEL[fine_label],
            "candidate_doc_count": len(candidates),
            "gold_evidence_doc_count": len(claim.get("evidence", {})),
            "annotation_files": " | ".join(annotation_files),
        })

    with (args.output / "gold_mapping.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=mappings[0].keys())
        writer.writeheader()
        writer.writerows(mappings)

    label_counts = Counter(row["project_label"] for row in mappings)
    fine_counts = Counter(row["fine_label"] for row in mappings)
    for k in sorted(set(args.top_k)):
        output_rows = []
        gold_total = 0
        gold_hit = 0
        claims_with_gold = 0
        claims_hit = 0
        for claim in claims:
            docs = rankings[claim["id"]][:k]
            output_rows.append({"id": claim["id"], "claim": claim["claim"], "doc_ids": docs})
            gold_docs = {int(doc_id) for doc_id in claim.get("evidence", {})}
            if gold_docs:
                claims_with_gold += 1
                hits = gold_docs & set(docs)
                gold_total += len(gold_docs)
                gold_hit += len(hits)
                claims_hit += int(bool(hits))
        write_jsonl(args.output / f"claims_dev_tfidf_top{k}.jsonl", output_rows)
        metrics = {
            "dataset": "Sarol 2024 dev",
            "retriever": "TF-IDF unigram + bigram within cited_doc_ids",
            "top_k": k,
            "claims": len(claims),
            "corpus_blocks": len(corpus),
            "gold_evidence_docs": gold_total,
            "retrieved_gold_evidence_docs": gold_hit,
            "evidence_document_recall": gold_hit / gold_total if gold_total else 0.0,
            "claims_with_gold_evidence": claims_with_gold,
            "claims_with_at_least_one_hit": claims_hit,
            "claim_level_retrieval_recall": claims_hit / claims_with_gold if claims_with_gold else 0.0,
        }
        (args.output / f"retrieval_metrics_top{k}.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(metrics, ensure_ascii=False))

    manifest = {
        "claims": len(claims),
        "corpus_blocks": len(corpus),
        "project_label_counts": dict(label_counts),
        "fine_label_counts": dict(fine_counts),
        "aggregation_protocol": "NOT_ACCURATE if any CONTRADICT prediction; else ACCURATE if any SUPPORT prediction; else IRRELEVANT",
        "note": "Raw fine labels are paired by stable order within each cited-paper group and verified against normalized citation_context text.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
