"""Build a deterministic, evidence-backed Sarol error-case package."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_CLAIMS = ROOT / "成员1反馈 Data" / "multivers-format" / "claims-dev.jsonl"
DEFAULT_CORPUS = ROOT / "成员1反馈 Data" / "multivers-format" / "corpus.jsonl"
DEFAULT_MAPPING = ROOT / "sarol_transfer_input" / "gold_mapping.csv"
DEFAULT_CANDIDATES = ROOT / "sarol_transfer_input" / "claims_dev_tfidf_top20.jsonl"
DEFAULT_TOP20 = ROOT / "experiment_results" / "sarol_open_tfidf_top20" / "predictions.jsonl"
DEFAULT_ORACLE = ROOT / "experiment_results" / "sarol_oracle.jsonl"
DEFAULT_OUTDIR = ROOT / "experiment_results" / "sarol_evidence_block_level"


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def normalized_gold_label(raw_label: str) -> str:
    if raw_label in {"ACCURATE", "INDIRECT", "INDIRECT_NOT_REVIEW"}:
        return "ACCURATE"
    if raw_label == "IRRELEVANT":
        return "IRRELEVANT"
    return "NOT_ACCURATE"


def aggregate(prediction: dict) -> tuple[str, bool]:
    labels = {entry.get("label") for entry in prediction.get("evidence", {}).values()}
    conflict = bool(labels & {"CONTRADICT", "REFUTES"}) and bool(
        labels & {"SUPPORT", "SUPPORTS"}
    )
    if labels & {"CONTRADICT", "REFUTES"}:
        return "NOT_ACCURATE", conflict
    if labels & {"SUPPORT", "SUPPORTS"}:
        return "ACCURATE", conflict
    return "IRRELEVANT", conflict


def compact_text(text: str, limit: int = 700) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def snippet(corpus: dict[str, dict], doc_id: str, sentence_ids: list[int]) -> dict:
    document = corpus.get(str(doc_id), {})
    sentences = document.get("abstract", [])
    items = []
    for sentence_id in sentence_ids:
        if isinstance(sentence_id, int) and 0 <= sentence_id < len(sentences):
            items.append(
                {
                    "sentence_id": sentence_id,
                    "text": compact_text(sentences[sentence_id]),
                }
            )
    return {
        "doc_id": str(doc_id),
        "title": compact_text(document.get("title", ""), 240),
        "sentences": items,
    }


def predicted_evidence(prediction: dict, corpus: dict[str, dict]) -> list[dict]:
    result = []
    for doc_id, entry in prediction.get("evidence", {}).items():
        result.append(
            {
                "doc_id": str(doc_id),
                "label": entry.get("label"),
                "sentences": entry.get("sentences", []),
                "text": snippet(corpus, str(doc_id), entry.get("sentences", [])),
            }
        )
    return result


def classify_reason(
    gold_label: str,
    top20_label: str,
    oracle_label: str,
    missing_gold_docs: list[str],
    top20_predicted_docs: list[str],
    conflict: bool,
) -> str:
    if conflict:
        return "同一论断同时出现 SUPPORT 和 CONTRADICT，按不支持优先规则汇总；需要人工核对证据冲突。"
    if top20_label == "IRRELEVANT" and gold_label != "IRRELEVANT":
        if oracle_label == "IRRELEVANT":
            return "即使输入金标准证据块，模型仍判为无关，主要指向跨数据集分类适配和阈值偏置。"
        if missing_gold_docs:
            return "前20候选未覆盖部分金标准证据，且模型未输出非无关证据；同时存在检索漏召回和分类偏置可能。"
        return "金标准证据已经在候选范围内，但前20结果仍判为无关，主要指向分类适配和阈值偏置。"
    if top20_label != gold_label:
        return "模型输出了非无关标签，但方向与 Sarol 项目级标签不一致，属于跨数据集标签方向错误。"
    if top20_predicted_docs and missing_gold_docs:
        return "项目级标签暂时正确，但候选集合漏掉部分金标准证据，属于检索覆盖风险。"
    return "需要结合证据文本进一步人工核对。"


def choose_cases(records: list[dict], limit: int = 20) -> list[dict]:
    by_bucket = {}
    for record in records:
        gold = record["gold_project_label"]
        pred = record["top20_project_prediction"]
        bucket = {
            ("NOT_ACCURATE", "IRRELEVANT"): "not_accurate_to_irrelevant",
            ("ACCURATE", "IRRELEVANT"): "accurate_to_irrelevant",
            ("NOT_ACCURATE", "ACCURATE"): "not_accurate_to_accurate",
            ("ACCURATE", "NOT_ACCURATE"): "accurate_to_not_accurate",
        }.get((gold, pred), "other_error")
        if record["oracle_project_prediction"] != pred:
            bucket = "oracle_top20_disagreement"
        if record["top20_conflict"]:
            bucket = "prediction_conflict"
        by_bucket.setdefault(bucket, []).append(record)

    bucket_order = [
        ("not_accurate_to_irrelevant", 6),
        ("accurate_to_irrelevant", 6),
        ("not_accurate_to_accurate", 3),
        ("accurate_to_not_accurate", 2),
        ("oracle_top20_disagreement", 2),
        ("prediction_conflict", 1),
    ]
    selected = []
    selected_ids = set()
    for bucket, quota in bucket_order:
        candidates = by_bucket.get(bucket, [])
        candidates = sorted(
            candidates,
            key=lambda record: (
                -len(record["missing_gold_doc_ids"]),
                record["claim_id_int"],
            ),
        )
        for record in candidates:
            if record["claim_id"] in selected_ids:
                continue
            selected.append(record)
            selected_ids.add(record["claim_id"])
            if sum(1 for item in selected if item["selection_bucket"] == bucket) >= quota:
                break

    remaining = sorted(
        [record for record in records if record["claim_id"] not in selected_ids],
        key=lambda record: (-len(record["missing_gold_doc_ids"]), record["claim_id_int"]),
    )
    for record in remaining:
        if len(selected) >= limit:
            break
        selected.append(record)
        selected_ids.add(record["claim_id"])

    selected.sort(key=lambda record: record["claim_id_int"])
    for index, record in enumerate(selected, start=1):
        record["case_no"] = index
    return selected[:limit]


def write_csv(path: Path, records: list[dict]):
    fields = [
        "case_no",
        "claim_id",
        "gold_fine_label",
        "gold_project_label",
        "oracle_project_prediction",
        "top20_project_prediction",
        "top20_conflict",
        "gold_evidence_doc_count",
        "missing_gold_doc_count",
        "predicted_doc_count",
        "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "case_no": record["case_no"],
                    "claim_id": record["claim_id"],
                    "gold_fine_label": "; ".join(record["gold_fine_labels"]),
                    "gold_project_label": record["gold_project_label"],
                    "oracle_project_prediction": record["oracle_project_prediction"],
                    "top20_project_prediction": record["top20_project_prediction"],
                    "top20_conflict": record["top20_conflict"],
                    "gold_evidence_doc_count": len(record["gold_evidence_doc_ids"]),
                    "missing_gold_doc_count": len(record["missing_gold_doc_ids"]),
                    "predicted_doc_count": len(record["top20_predicted_evidence"]),
                    "reason": record["reason"],
                }
            )


def write_readme(path: Path, records: list[dict], all_errors: list[dict]):
    counts = Counter(
        (record["gold_project_label"], record["top20_project_prediction"])
        for record in all_errors
    )
    lines = [
        "Sarol 2024 错误案例包",
        "",
        "本目录保存 Sarol 开发集的证据块级诊断和 20 条代表性论断级错误案例。",
        "案例来自本地已下载的开发集、金标准证据、金标准证据预测和 TF-IDF 前20预测。",
        "",
        f"开发集错误论断总数：{len(all_errors)}",
        f"抽取代表性案例数：{len(records)}",
        "",
        "全量前20预测错误分布：",
    ]
    for (gold, pred), count in sorted(counts.items()):
        lines.append(f"真实 {gold}，预测 {pred}：{count} 条")
    lines.extend(
        [
            "",
            "注意：金标准证据块输入与 TF-IDF 前20输入不是同一候选规模，不能把两者的论断级分数直接当作检索器优劣。",
            "本目录中的证据块级指标用于定位跨数据集分类和无关类偏置，不替代正式的三分类总体指标。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--top20", type=Path, default=DEFAULT_TOP20)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    claims = load_jsonl(args.claims)
    corpus = {str(row["doc_id"]): row for row in load_jsonl(args.corpus)}
    candidates = {str(row["id"]): row for row in load_jsonl(args.candidates)}
    top20 = {str(row["id"]): row for row in load_jsonl(args.top20)}
    oracle = {str(row["id"]): row for row in load_jsonl(args.oracle)}
    with args.mapping.open(encoding="utf-8-sig", newline="") as stream:
        mapping_rows = list(csv.DictReader(stream))
    mapping = {str(row["claim_id"]): row for row in mapping_rows}

    records = []
    for claim in claims:
        claim_id = str(claim["id"])
        gold_row = mapping[claim_id]
        gold_label = gold_row["project_label"]
        gold_doc_ids = [str(doc_id) for doc_id in claim.get("evidence", {})]
        candidate_doc_ids = {
            str(doc_id) for doc_id in candidates.get(claim_id, {}).get("doc_ids", [])
        }
        missing_gold_doc_ids = sorted(set(gold_doc_ids) - candidate_doc_ids)
        oracle_label, oracle_conflict = aggregate(oracle.get(claim_id, {}))
        top20_label, top20_conflict = aggregate(top20.get(claim_id, {}))
        if top20_label == gold_label:
            continue

        gold_evidence = []
        fine_labels = []
        for doc_id, entries in claim.get("evidence", {}).items():
            fine_labels.extend(entry["label"] for entry in entries)
            gold_evidence.append(
                {
                    "doc_id": str(doc_id),
                    "fine_labels": [entry["label"] for entry in entries],
                    "sentences": [entry["sentences"] for entry in entries],
                    "text": snippet(
                        corpus,
                        str(doc_id),
                        sorted(
                            {
                                sentence_id
                                for entry in entries
                                for sentence_id in entry["sentences"]
                            }
                        ),
                    ),
                }
            )

        predicted = predicted_evidence(top20.get(claim_id, {}), corpus)
        reason = classify_reason(
            gold_label,
            top20_label,
            oracle_label,
            missing_gold_doc_ids,
            [entry["doc_id"] for entry in predicted],
            top20_conflict,
        )
        records.append(
            {
                "claim_id": claim_id,
                "claim_id_int": int(claim["id"]),
                "claim": claim["claim"],
                "gold_fine_labels": sorted(set(fine_labels)),
                "mapping_fine_label": gold_row.get("fine_label", ""),
                "gold_project_label": gold_label,
                "oracle_project_prediction": oracle_label,
                "oracle_conflict": oracle_conflict,
                "top20_project_prediction": top20_label,
                "top20_conflict": top20_conflict,
                "gold_evidence_doc_ids": gold_doc_ids,
                "candidate_doc_count": len(candidate_doc_ids),
                "missing_gold_doc_ids": missing_gold_doc_ids,
                "gold_evidence": gold_evidence,
                "oracle_predicted_evidence": predicted_evidence(oracle.get(claim_id, {}), corpus),
                "top20_predicted_evidence": predicted,
                "reason": reason,
                "selection_bucket": "",
            }
        )

    for record in records:
        if record["top20_conflict"]:
            record["selection_bucket"] = "prediction_conflict"
        elif record["oracle_project_prediction"] != record["top20_project_prediction"]:
            record["selection_bucket"] = "oracle_top20_disagreement"
        else:
            record["selection_bucket"] = {
                ("NOT_ACCURATE", "IRRELEVANT"): "not_accurate_to_irrelevant",
                ("ACCURATE", "IRRELEVANT"): "accurate_to_irrelevant",
                ("NOT_ACCURATE", "ACCURATE"): "not_accurate_to_accurate",
                ("ACCURATE", "NOT_ACCURATE"): "accurate_to_not_accurate",
            }.get(
                (record["gold_project_label"], record["top20_project_prediction"]),
                "other_error",
            )

    selected = choose_cases(records, args.limit)
    args.outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": "Sarol 2024 representative error cases",
        "source": {
            "claims": str(args.claims),
            "corpus": str(args.corpus),
            "mapping": str(args.mapping),
            "candidates": str(args.candidates),
            "top20_predictions": str(args.top20),
            "oracle_predictions": str(args.oracle),
        },
        "all_claim_errors": len(records),
        "selected_cases": len(selected),
        "selection_note": "按错误方向、Oracle/前20分歧和预测冲突分层抽取；证据文本来自本地 corpus.jsonl。",
        "cases": selected,
    }
    (args.outdir / "error_cases_20.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(args.outdir / "error_cases_20.csv", selected)
    write_readme(args.outdir / "README.txt", selected, records)

    copies = [
        (args.outdir / "metrics_sarol_evidence_block.json", ROOT / "experiment_results" / "metrics_sarol_evidence_block.json"),
        (args.outdir / "metrics_sarol_oracle_vs_top20.json", ROOT / "experiment_results" / "metrics_sarol_oracle_vs_top20.json"),
        (args.outdir / "sarol_oracle.jsonl", args.oracle),
        (args.outdir / "sarol_top20_predictions.jsonl", args.top20),
    ]
    for destination, source in copies:
        if source.exists():
            shutil.copy2(source, destination)

    print(json.dumps({"all_claim_errors": len(records), "selected_cases": len(selected), "outdir": str(args.outdir)}, ensure_ascii=False, indent=2))
    print("error_direction_counts:", dict(Counter((r["gold_project_label"], r["top20_project_prediction"]) for r in records)))
    print("selection_buckets:", dict(Counter(r["selection_bucket"] for r in selected)))


if __name__ == "__main__":
    main()
