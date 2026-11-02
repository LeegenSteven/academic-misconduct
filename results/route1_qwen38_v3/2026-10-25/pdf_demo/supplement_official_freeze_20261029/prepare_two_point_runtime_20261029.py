"""Prepare and run the two-point supplement frozen on 2026-10-29.

The script is intentionally separate from the historical 13-point runtime.
It creates only the two frozen supplement inputs and never mutates the original
20-point or 13-point artifacts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import fitz


HERE = Path(__file__).resolve().parent
CODE = HERE.parents[4] / "code" / "ly"
WORKSPACE = HERE.parents[5]
SOURCE_ROOT = WORKSPACE / "10.19-11.2" / "路线一PDF独立清单_20261020"
MANIFEST = HERE / "official_supplement_manifest.jsonl"
PAIR_MANIFEST = SOURCE_ROOT / "pair_manifest.jsonl"
VERSION = "supplement_two_point_runtime_20261029"
ADAPTER_SHA = "0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09"
BASE_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
MAX_LENGTH, MAX_NEW = 5120, 512
SETTINGS = {"max_length": MAX_LENGTH, "max_new_tokens": MAX_NEW,
            "enable_thinking": False, "do_sample": False,
            "retry_policy": "none; keep all first attempts"}
CLASSIFIER_SYSTEM = (
    "你是学术引文核验助手。只依据给出的候选证据核查当前目标引用，不使用外部知识。\n"
    "只判断目标引用覆盖的原文片段；必要上下文仅用于解消指代，不是额外核查主张。"
    "同句其他文献对应的分句不能转嫁给当前目标文献。不能删掉目标主张中的数字、比较方向、对象或条件。\n"
    "标签定义：\n"
    "ACCURATE：候选证据直接支持目标主张的实质内容，且没有重要歪曲。\n"
    "NOT_ACCURATE：候选证据与目标主张矛盾，或主张存在重要的未获支持、错误转述、过度简化或归属错误。\n"
    "IRRELEVANT：候选证据与目标主张没有实质关联，无法用于支持或反驳。\n"
    "正常判定只输出一个含 label 的 JSON 对象，不输出理由、置信度或额外字段。"
    "若候选证据不足以判定，不把证据不足直接改成 IRRELEVANT，输出"
    '{"failure_status":"insufficient_evidence"}。失败状态不是第四类标签。'
)
EXPLAINER_SYSTEM = (
    "你是独立的学术引用证据解释模块，不是分类器。只依据当前被引文献的候选原文，核查目标引用覆盖的主张。"
    "必要上下文只用于解消指代。同句其他引用的主张不能归给当前文献。保留对象、数量、方向和条件；部分支持不能写成全部支持。"
    "不要使用外部知识，不推测缺失证据，不输出分类标签或置信度。"
    "仅输出JSON：{\"evidence_ids\":[\"D01:S01\"],\"quotes\":[{\"evidence_id\":\"D01:S01\",\"quote\":\"候选原文中连续、逐字一致的简短摘录\"}],\"reason\":\"说明证据支持、反驳或不能解决哪些具体主张，并明确限制\"}。"
    "编号只能来自所给候选；每个选中编号至少一处摘录，换行及符号也须原样保留。理由必须有证据，不得过度概括。"
    "若无法取得足够证据，只输出{\"failure_status\":\"insufficient_evidence\"}。"
)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def digest(value) -> str:
    return sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8", newline="\n")


def block_fragment(pdf_path: Path, page_no: int, block_no: int, start: int, end: int) -> dict:
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_no - 1]
        page_text = page.get_text("text", sort=False)
        raw = page_text[start:end]
        blocks = []
        cursor = 0
        for number, block in enumerate(page.get_text("blocks", sort=False), 1):
            if len(block) > 6 and block[6] != 0:
                continue
            block_text = str(block[4])
            block_start = page_text.find(block_text, cursor)
            if block_start < 0:
                continue
            cursor = block_start + len(block_text)
            if block_start < end and start < cursor:
                blocks.append({"block_number": number, "bbox": [round(float(x), 3) for x in block[:4]]})
        if not raw or not blocks:
            raise ValueError(f"Cannot replay fragment {pdf_path.name} p{page_no} [{start},{end})")
        return {"pdf_page": page_no, "printed_page": None, "char_start": start,
                "char_end_exclusive": end, "raw_text": raw,
                "raw_text_sha256": sha_bytes(raw.encode("utf-8")),
                "source_blocks": blocks,
                "bbox_scope": "whole intersecting text blocks, not exact sentence boxes",
                "offset_basis": "PyMuPDF page.get_text(text, sort=False); Unicode code points; zero-based half-open"}
    finally:
        doc.close()


def candidate(pdf_path: Path, pdf_sha: str, rank: int, fragment: dict) -> dict:
    text = fragment["raw_text"]
    return {"evidence_id": f"D01:S{rank:02d}", "retrieval_rank": rank,
            "source_pdf_sha256": pdf_sha, "pdf_fragments": [fragment],
            "raw_text": text, "raw_text_sha256": fragment["raw_text_sha256"],
            "model_text": text, "model_text_sha256": fragment["raw_text_sha256"],
            "correction_patch_ids": []}


def prompt(claim: str, candidates: list[dict], explainer: bool) -> str:
    lines = ["目标引用覆盖的原文片段：", claim, "候选证据："]
    lines.extend(f"{c['evidence_id']} | {c['model_text']}" for c in candidates)
    lines.append("仅返回规定的证据摘录和解释 JSON，不输出分类标签。" if explainer
                 else "仅对目标引用范围返回 label JSON；不能可靠判定时返回规定的 failure_status。")
    return "\n".join(lines)


def make_items() -> list[dict]:
    frozen = read_jsonl(MANIFEST)
    pairs = {r["pair_id"]: r for r in read_jsonl(PAIR_MANIFEST)}
    items = []
    for row in frozen:
        pair = pairs[row["pair_id"]]
        cited_path = SOURCE_ROOT / row["cited_pdf_relative_path"]
        cited_sha = row["cited_pdf_sha256"]
        if sha(cited_path) != cited_sha:
            raise ValueError(f"Cited PDF hash mismatch: {cited_path}")
        locs = row["cited_evidence_locators"]
        fragments = [block_fragment(cited_path, x["pdf_page"], x["block_number"], x["char_start"], x["char_end_exclusive"]) for x in locs]
        candidates = [candidate(cited_path, cited_sha, i + 1, f) for i, f in enumerate(fragments)]
        claim = row["proposed_target_claim"]
        cuser = prompt(claim, candidates, False)
        euser = prompt(claim, candidates, True)
        classifier = {"claim_id": row["case_id"], "system_prompt": CLASSIFIER_SYSTEM,
                      "user_prompt": cuser, "input_sha256": digest({"system_prompt": CLASSIFIER_SYSTEM, "user_prompt": cuser}),
                      "candidate_evidence": candidates, "scope_hold": None,
                      "stage": "frozen_two_point_prepared_not_run"}
        explainer = {"claim_id": row["case_id"], "system_prompt": EXPLAINER_SYSTEM,
                     "user_prompt": euser, "input_sha256": digest({"system_prompt": EXPLAINER_SYSTEM, "user_prompt": euser}),
                     "stage": "frozen_two_point_prepared_not_run"}
        items.append({"case_id": row["case_id"], "pair_id": row["pair_id"],
                      "reference_id": row["reference_id"], "citing_pdf_sha256": row["citing_pdf_sha256"],
                      "cited_pdf_sha256": cited_sha, "target_scope_code": row["target_scope_code"],
                      "claim": claim, "citation_marker_locator": row["citation_marker_locator"],
                      "excluded_claims": row.get("excluded_claims", []), "retrieval": {"candidates": candidates,
                      "method": "frozen_locator_evidence_only", "source_pdf_sha256": cited_sha},
                      "classifier": classifier, "explainer": explainer,
                      "source_pair": {"citing": pair["citing"], "cited": pair["cited"]}})
    return items


def prepare() -> None:
    items = make_items()
    write_jsonl(HERE / "prepared_items.jsonl", items)
    write_jsonl(HERE / "classification.inputs.jsonl", [x["classifier"] for x in items])
    write_jsonl(HERE / "explanation.inputs.jsonl", [x["explainer"] for x in items])
    plan = {"version": VERSION, "status": "A100_REQUIRED_NOT_STARTED", "scope": "two_frozen_supplements_only",
            "selected_case_ids": [x["case_id"] for x in items], "fixed_denominator": 20,
            "model": {"base": "Qwen/Qwen3.8-27B", "revision": BASE_REVISION, "adapter": "Mbio/checkpoint-100", "adapter_sha256": ADAPTER_SHA},
            "stages": ["classifier", "explainer"], "settings": SETTINGS,
            "retry_policy": "none_keep_first_attempt", "source_validation": "actual_PDF_replayed",
            "original_18_reuse": True, "held_points": [1, 15], "human_locator_review": "pending_after_model_outputs",
            "prepared_items_sha256": sha(HERE / "prepared_items.jsonl"),
            "classification_inputs_sha256": sha(HERE / "classification.inputs.jsonl"),
            "explanation_inputs_sha256": sha(HERE / "explanation.inputs.jsonl"),
            "code_sha256": sha(Path(__file__))}
    write_json(HERE / "two_point_runtime_plan.json", plan)
    receipt = {"version": VERSION, "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
               "status": "PREPARED_FOR_A100_NOT_RUN", "model_run_started": False,
               "plan_sha256": sha(HERE / "two_point_runtime_plan.json"), "points": len(items),
               "candidate_locators_replayed": sum(len(x["retrieval"]["candidates"]) for x in items),
               "local_nvidia_smi": False,
               "note": "This package does not contain model responses; no run or acceptance is inferred."}
    write_json(HERE / "preparation_receipt.json", receipt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare",))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
        print("PREPARED two-point frozen supplement inputs; A100 run not started")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
