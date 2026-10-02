from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()
    if not text:
        return [""]
    # SciCiteVal provides evidence paragraphs/abstracts rather than sentence
    # offsets. This deterministic splitter is only used to feed MultiVerS;
    # sentence-level scores are therefore not treated as gold evidence scores.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\[(\"'])", text)
    return [part.strip() for part in parts if part.strip()]


def stable_doc_id(text: str, index: int) -> int:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return 100000000 + index


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Convert SciCiteVal to a MultiVerS transfer-evaluation format.")
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "成员2_交付" / "data" / "sciciteval_repo" / "experiment_dataset.tsv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "sciciteval_transfer_input",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    required = {"Citation_context", "Cited_content", "Label", "Twist_category"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    group_to_doc: dict[str, int] = {}
    corpus = []
    claims = []
    gold = []
    mapping = []
    for row_id, row in enumerate(rows):
        cited = row["Cited_content"].strip()
        if cited not in group_to_doc:
            doc_id = stable_doc_id(cited, len(group_to_doc))
            group_to_doc[cited] = doc_id
            corpus.append({
                "doc_id": doc_id,
                "title": "SciCiteVal evidence group",
                "abstract": split_sentences(cited),
                "structured": False,
            })
        doc_id = group_to_doc[cited]
        label = row["Label"].strip()
        if label not in {"Correct", "Incorrect", "Unrelated"}:
            raise ValueError(f"Unexpected label at row {row_id}: {label}")
        model_label = {"Correct": "SUPPORT", "Incorrect": "CONTRADICT", "Unrelated": None}[label]
        sentences = next(doc["abstract"] for doc in corpus if doc["doc_id"] == doc_id)
        claims.append({"id": row_id, "claim": row["Citation_context"].strip(), "doc_ids": [doc_id]})
        if model_label is None:
            gold.append({"id": row_id, "evidence": {}})
        else:
            gold.append({
                "id": row_id,
                "evidence": {str(doc_id): [{"label": model_label, "sentences": list(range(len(sentences)))}]},
            })
        mapping.append({
            "row_id": row_id,
            "doc_id": doc_id,
            "gold_label": label,
            "model_label": model_label or "NEI",
            "twist_category": row["Twist_category"].strip(),
        })

    def write_jsonl(name, data):
        with (args.output / name).open("w", encoding="utf-8") as stream:
            for item in data:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_jsonl("corpus.jsonl", corpus)
    write_jsonl("claims.jsonl", claims)
    write_jsonl("gold.jsonl", gold)
    with (args.output / "mapping.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=mapping[0].keys())
        writer.writeheader()
        writer.writerows(mapping)
    manifest = {
        "source": str(args.input),
        "rows": len(rows),
        "unique_cited_content": len(corpus),
        "label_counts": {label: sum(row["Label"].strip() == label for row in rows) for label in ["Correct", "Incorrect", "Unrelated"]},
        "protocol": "Correct->SUPPORT, Incorrect->CONTRADICT, Unrelated->NEI; each unique Cited_content is one synthetic corpus document",
        "sentence_metric_note": "SciCiteVal has no unified sentence-offset gold field; sentence-level scores are not reported as gold evidence scores.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
