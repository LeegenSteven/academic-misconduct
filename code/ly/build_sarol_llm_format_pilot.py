from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "成员2_20条大模型格式验证_2026-09-17"
SAMPLE_IDS = [
    0, 19, 21, 188, 193, 222, 289,
    24, 69, 1, 59, 12, 135, 42, 4, 145,
    52, 127, 283, 300,
]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def find_one(pattern: str) -> Path:
    matches = list(ROOT.glob(pattern))
    if not matches:
        raise FileNotFoundError(pattern)
    return matches[0]


def main() -> None:
    claims_path = find_one("**/multivers-format/claims-dev.jsonl")
    corpus_path = claims_path.with_name("corpus.jsonl")
    candidates_path = ROOT / "sarol_transfer_input" / "claims_dev_tfidf_top20.jsonl"
    mapping_path = ROOT / "sarol_transfer_input" / "gold_mapping.csv"

    claims = {int(row["id"]): row for row in load_jsonl(claims_path)}
    corpus = {str(row["doc_id"]): row for row in load_jsonl(corpus_path)}
    candidates = {int(row["id"]): row for row in load_jsonl(candidates_path)}
    with mapping_path.open(encoding="utf-8-sig", newline="") as stream:
        mapping = {int(row["claim_id"]): row for row in csv.DictReader(stream)}

    OUTPUT.mkdir(exist_ok=True)
    system_prompt = (
        "你是学术引文核验助手。只依据给出的候选证据判断引用论断，不使用外部知识。\n"
        "标签定义：\n"
        "ACCURATE：候选证据直接支持论断的实质内容，且没有重要歪曲。\n"
        "NOT_ACCURATE：候选证据与论断矛盾，或论断存在重要的未获支持、错误转述、过度简化或归属错误。\n"
        "IRRELEVANT：候选证据与论断没有实质关联，无法用于支持或反驳。\n"
        "必须输出一个 JSON 对象，不要输出 Markdown。evidence_ids 只能从候选证据编号中选择，最多 5 个；"
        "reason 使用中文且不超过 120 个汉字；confidence 为 0 到 1 的小数。"
    )
    (OUTPUT / "prompt_template.md").write_text(
        "# Sarol 20条大模型格式验证提示词\n\n"
        "## System prompt\n\n" + system_prompt +
        "\n\n## User prompt template\n\n"
        "```text\nclaim_id: {claim_id}\n引用论断：{claim}\n候选证据：\n{evidence}\n\n"
        "请按 schema 返回 JSON。\n```\n",
        encoding="utf-8",
    )

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["claim_id", "label", "evidence_ids", "reason", "confidence", "failure_status"],
        "properties": {
            "claim_id": {"type": "integer"},
            "label": {"enum": ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]},
            "evidence_ids": {
                "type": "array",
                "maxItems": 5,
                "uniqueItems": True,
                "items": {"type": "string", "pattern": "^D[0-9]{2}:S[0-9]{2}$"},
            },
            "reason": {"type": "string", "minLength": 1, "maxLength": 120},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "failure_status": {"type": ["string", "null"]},
        },
    }
    (OUTPUT / "output_schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest_rows = []
    input_rows = []
    readable = []
    for order, claim_id in enumerate(SAMPLE_IDS, start=1):
        claim = claims[claim_id]
        gold = mapping[claim_id]
        candidate_docs = candidates[claim_id]["doc_ids"]
        evidence = []
        for doc_order, doc_id in enumerate(candidate_docs, start=1):
            doc = corpus[str(doc_id)]
            title = doc.get("title", "")
            if title:
                evidence.append({
                    "evidence_id": f"D{doc_order:02d}:S00",
                    "doc_id": int(doc_id),
                    "sentence_id": 0,
                    "text": f"[TITLE] {title}",
                })
            for sentence_id, text in enumerate(doc.get("abstract", []), start=1):
                evidence.append({
                    "evidence_id": f"D{doc_order:02d}:S{sentence_id:02d}",
                    "doc_id": int(doc_id),
                    "sentence_id": sentence_id - 1,
                    "text": text,
                })

        user_lines = [f"claim_id: {claim_id}", f"引用论断：{claim['claim']}", "候选证据："]
        for item in evidence:
            user_lines.append(f"{item['evidence_id']} | doc_id={item['doc_id']} | {item['text']}")
        user_lines.append("请按 schema 返回 JSON。")
        input_rows.append({
            "sample_order": order,
            "claim_id": claim_id,
            "system_prompt": system_prompt,
            "user_prompt": "\n".join(user_lines),
            "allowed_evidence_ids": [item["evidence_id"] for item in evidence],
            "candidate_evidence": evidence,
        })
        manifest_rows.append({
            "sample_order": order,
            "claim_id": claim_id,
            "fine_label": gold["fine_label"],
            "project_label": gold["project_label"],
            "gold_evidence_doc_count": gold["gold_evidence_doc_count"],
            "candidate_doc_count": len(candidate_docs),
            "selection_group": (
                "ACCURATE_OR_INDIRECT" if gold["project_label"] == "ACCURATE"
                else "NOT_ACCURATE" if gold["project_label"] == "NOT_ACCURATE"
                else "IRRELEVANT"
            ),
        })
        readable.append("\n".join(user_lines))

    with (OUTPUT / "fixed_sample_manifest.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    (OUTPUT / "model_inputs.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in input_rows), encoding="utf-8"
    )
    (OUTPUT / "review_inputs.txt").write_text(
        ("\n" + "=" * 100 + "\n").join(readable), encoding="utf-8"
    )

    distribution = Counter(row["project_label"] for row in manifest_rows)
    fine_distribution = Counter(row["fine_label"] for row in manifest_rows)
    summary = {
        "sample_count": len(manifest_rows),
        "sample_ids": SAMPLE_IDS,
        "project_label_distribution": dict(distribution),
        "fine_label_distribution": dict(fine_distribution),
        "input_source": "TF-IDF top-20 fixed candidate blocks",
        "gold_leakage_control": "Gold labels are only in fixed_sample_manifest.csv, never in model_inputs.jsonl prompts.",
    }
    (OUTPUT / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
