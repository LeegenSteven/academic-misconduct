"""Validate and rescore the Dev contrast files supplied by member 1."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "成员1_Dev对照材料_2026-09-13"
CLAIMS = ROOT / "成员1反馈 Data" / "multivers-format" / "claims-dev.jsonl"
CORPUS = ROOT / "成员1反馈 Data" / "multivers-format" / "corpus.jsonl"
MAPPING = ROOT / "sarol_transfer_input" / "gold_mapping.csv"


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def confusion(rows, prediction_key):
    matrix = Counter((row["gold"], row[prediction_key]) for row in rows)
    total = len(rows)
    accuracy = sum(matrix[(label, label)] for label in {"ACCURATE", "NOT_ACCURATE", "NEI"}) / total
    per_class = {}
    for label in ("ACCURATE", "NOT_ACCURATE", "NEI"):
        tp = matrix[(label, label)]
        predicted = sum(matrix[(gold, label)] for gold in {"ACCURATE", "NOT_ACCURATE", "NEI"})
        gold = sum(matrix[(label, pred)] for pred in {"ACCURATE", "NOT_ACCURATE", "NEI"})
        precision = tp / predicted if predicted else 0.0
        recall = tp / gold if gold else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1}
    return {
        "accuracy": accuracy,
        "macro_f1": sum(value["f1"] for value in per_class.values()) / 3,
        "per_class": per_class,
        "prediction_counts": dict(Counter(row[prediction_key] for row in rows)),
        "confusion_matrix": {
            gold: {pred: matrix[(gold, pred)] for pred in ("ACCURATE", "NOT_ACCURATE", "NEI")}
            for gold in ("ACCURATE", "NOT_ACCURATE", "NEI")
        },
    }


def main():
    claims = load_jsonl(CLAIMS)
    corpus = {str(row["doc_id"]): row for row in load_jsonl(CORPUS)}
    rows_a = load_jsonl(SOURCE / "dev_gold_input_predictions.jsonl")
    rows_b = load_jsonl(SOURCE / "dev_bm25_input_predictions.jsonl")
    input_a = load_jsonl(SOURCE / "dev_gold_input.jsonl")
    input_b = load_jsonl(SOURCE / "dev_bm25_input.jsonl")
    result_raw = json.loads((SOURCE / "multivers_dev_contrast_result.json").read_text(encoding="utf-8"))

    assert len(claims) == 316
    assert len(rows_a) == len(rows_b) == len(input_a) == len(input_b) == 316
    ids = {str(row["id"]) for row in claims}
    assert {str(row["claim_id"]) for row in rows_a} == ids
    assert {str(row["claim_id"]) for row in rows_b} == ids
    assert {str(row["claim_id"]) for row in input_a} == ids
    assert {str(row["claim_id"]) for row in input_b} == ids
    claim_lookup = {str(row["id"]): row for row in claims}

    for row in rows_a + rows_b:
        claim_id = str(row["claim_id"])
        assert row["claim"] == claim_lookup[claim_id]["claim"]
        assert row["gold"] in {"ACCURATE", "NOT_ACCURATE", "NEI"}
        assert row["prediction"] in {"ACCURATE", "NOT_ACCURATE", "NEI"}
        for evidence in row.get("evidence", []):
            doc_id = str(evidence["doc_id"])
            sentence_index = evidence["sentence_index"]
            assert doc_id in corpus
            sentences = corpus[doc_id].get("abstract", [])
            assert isinstance(sentence_index, int) and 0 <= sentence_index < len(sentences)
            assert normalize(evidence["text"]) == normalize(sentences[sentence_index])

    for input_row in input_a + input_b:
        assert input_row["claim"] == claim_lookup[str(input_row["claim_id"])]["claim"]
        assert "evidence_sentences" in input_row

    gold_doc_sets = {
        str(row["id"]): {str(doc_id) for doc_id in row.get("evidence", {})}
        for row in claims
    }
    bm25_doc_sets = {
        str(row["claim_id"]): {str(evidence["doc_id"]) for evidence in row.get("evidence", [])}
        for row in rows_b
    }
    claims_with_gold = {claim_id for claim_id, docs in gold_doc_sets.items() if docs}
    gold_doc_count = sum(len(docs) for docs in gold_doc_sets.values())
    retrieved_gold_doc_count = sum(
        len(gold_doc_sets[claim_id] & bm25_doc_sets[claim_id]) for claim_id in ids
    )
    claims_with_hit = sum(
        bool(gold_doc_sets[claim_id] & bm25_doc_sets[claim_id]) for claim_id in claims_with_gold
    )
    bm25_candidate_sentence_count = sum(len(row.get("evidence", [])) for row in rows_b)

    gold_by_id = {str(row["claim_id"]): row for row in rows_a}
    bm25_by_id = {str(row["claim_id"]): row for row in rows_b}
    rows = []
    for claim_id in sorted(ids, key=int):
        assert gold_by_id[claim_id]["gold"] == bm25_by_id[claim_id]["gold"]
        rows.append(
            {
                "claim_id": claim_id,
                "gold": gold_by_id[claim_id]["gold"],
                "gold_input_prediction": gold_by_id[claim_id]["prediction"],
                "bm25_input_prediction": bm25_by_id[claim_id]["prediction"],
            }
        )

    local = {
        "task": "Sarol Dev two-input contrast validation",
        "claims": len(rows),
        "gold_distribution": dict(Counter(row["gold"] for row in rows)),
        "gold_input": confusion(
            [{"gold": row["gold"], "prediction": row["gold_input_prediction"]} for row in rows],
            "prediction",
        ),
        "bm25_input": confusion(
            [{"gold": row["gold"], "prediction": row["bm25_input_prediction"]} for row in rows],
            "prediction",
        ),
        "prediction_agreement_count": sum(
            row["gold_input_prediction"] == row["bm25_input_prediction"] for row in rows
        ),
        "prediction_agreement_rate": sum(
            row["gold_input_prediction"] == row["bm25_input_prediction"] for row in rows
        )
        / len(rows),
        "bm25_candidate_sentence_count": bm25_candidate_sentence_count,
        "gold_evidence_document_count": gold_doc_count,
        "retrieved_gold_evidence_document_count": retrieved_gold_doc_count,
        "evidence_document_recall": retrieved_gold_doc_count / gold_doc_count,
        "claims_with_gold_evidence": len(claims_with_gold),
        "claims_with_at_least_one_bm25_hit": claims_with_hit,
        "claim_level_retrieval_recall": claims_with_hit / len(claims_with_gold),
        "source_summary": {
            "accuracy_gold_input": result_raw["accuracy_gold_input"],
            "accuracy_bm25_input": result_raw["accuracy_bm25_input"],
            "elapsed_seconds": result_raw["elapsed_seconds"],
        },
        "input_text_crosscheck": "All evidence texts and BM25 candidate texts match corpus.jsonl by doc_id and sentence_index.",
        "interpretation_note": "The evidence arrays in member-1 prediction files are input evidence/candidates, not model rationale output; top-level prediction is the model verdict.",
    }
    # Member 1's summary intentionally rounds accuracy to four decimal places.
    assert round(local["gold_input"]["accuracy"], 4) == round(
        result_raw["accuracy_gold_input"], 4
    )
    assert round(local["bm25_input"]["accuracy"], 4) == round(
        result_raw["accuracy_bm25_input"], 4
    )
    assert local["prediction_agreement_count"] == 265

    output = ROOT / "experiment_results" / "sarol_member1_dev_contrast"
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics_validated.json").write_text(json.dumps(local, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "claim_level_predictions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    print(json.dumps(local, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
