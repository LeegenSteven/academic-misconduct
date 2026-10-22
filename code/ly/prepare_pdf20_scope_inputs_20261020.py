"""Prepare source-mapped scope drafts, one explicit glyph correction and CPU budgets.

Does not write into the source package, assign semantic labels, load weights,
execute GPU inference, or claim two-person adjudication. Every point is retained.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import unicodedata

import run_route1_pdf_v3 as gate
from replay_cmj_pdf20_retrieval_20261020 import original_functions

BASE_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
TOKENIZER_FILES = {
    "tokenizer.json": "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3",
    "tokenizer_config.json": "b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27",
    "config.json": "191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab",
    "chat_template.jinja": "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041",
}
PROMPT_VERSION = "route1_pdf_scope_label_only_draft_v1_20261020"
SYSTEM_PROMPT = (
    "你是学术引文核验助手。只依据给出的候选证据核查当前目标引用，不使用外部知识。\n"
    "只判断目标引用覆盖的原文片段；必要上下文仅用于解消指代，不是额外核查主张。"
    "同句其他文献对应的分句不能转嫁给当前目标文献。不能删掉目标主张中的数字、比较方向、对象或条件。\n"
    "标签定义：\n"
    "ACCURATE：候选证据直接支持目标主张的实质内容，且没有重要歪曲。\n"
    "NOT_ACCURATE：候选证据与目标主张矛盾，或主张存在重要的未获支持、错误转述、过度简化或归属错误。\n"
    "IRRELEVANT：候选证据与目标主张没有实质关联，无法用于支持或反驳。\n"
    "正常判定只输出一个含 label 的 JSON 对象，label 为上述三类之一，不输出理由、置信度或额外字段。"
    "若候选证据不足以判定，不把证据不足直接改成 IRRELEVANT，输出"
    '{"failure_status":"insufficient_evidence"}。失败状态不是第四类标签。'
)


def normalized_with_map(fragments):
    chars, origins = [], []
    for fi, fragment in enumerate(fragments):
        if fi:
            chars.append("\n")
            origins.append(None)
        for offset, char in enumerate(fragment["raw_text"]):
            for normalized in unicodedata.normalize("NFKC", char):
                if normalized != "\u00ad":
                    chars.append(normalized)
                    origins.append((fi, fragment["char_start"] + offset))
    text = "".join(chars)
    deleted = set()
    for match in re.finditer(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", text):
        deleted.update(range(match.start(), match.end()))
    pairs = [(c, origin) for i, (c, origin) in enumerate(zip(chars, origins)) if i not in deleted]
    result, mapping = [], []
    for char, origin in pairs:
        if char.isspace():
            if result and result[-1] != " ":
                result.append(" ")
                mapping.append(origin)
        else:
            result.append(char)
            mapping.append(origin)
    if result and result[-1] == " ":
        result.pop()
        mapping.pop()
    return "".join(result), mapping


def normalize(text):
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    text = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def selector_span(case, selector):
    text = case["citing_context"]
    if selector.get("old_query"):
        wanted = case["target_claim_scope_proposal"]
        gate.require(text.count(wanted) == 1, "Old proposed scope is not unique in paragraph")
        start = text.index(wanted)
        return start, start + len(wanted)
    start = text.index(selector["start"])
    gate.require(text.count(selector["start"]) == 1, "Scope start anchor is ambiguous")
    end = text.index(selector["end"], start) + len(selector["end"])
    return start, end


def located_piece(case, selector, mapping, cached, replay, document):
    a, b = selector_span(case, selector)
    by_fragment = defaultdict(list)
    for origin in mapping[a:b]:
        if origin is not None:
            by_fragment[origin[0]].append(origin[1])
    fragments = []
    for fi, offsets in sorted(by_fragment.items()):
        old = case["citing_context_raw_fragments"][fi]
        start, end = min(offsets), max(offsets) + 1
        raw = old["raw_text"][start - old["char_start"]:end - old["char_start"]]
        boxes = [{"block_number": block["block_number"], "bbox": block["bbox"]} for block in cached
                 if block["pdf_page"] == old["pdf_page"] and block["char_start"] < end and start < block["char_end_exclusive"]]
        fragment = {"pdf_page": old["pdf_page"], "printed_page": None, "char_start": start,
                    "char_end_exclusive": end, "raw_text": raw, "raw_text_sha256": gate.text_sha(raw),
                    "source_blocks": boxes, "offset_basis": gate.OFFSET_BASIS, "bbox_scope": gate.BBOX_SCOPE}
        replay.fragment(document, fragment)
        fragments.append(fragment)
    wanted = case["citing_context"][a:b]
    gate.require(normalize("\n".join(f["raw_text"] for f in fragments)) == wanted,
                 "Mapped scope differs from unchanged PDF; no fuzzy acceptance")
    return {"text": wanted, "normalized_context_start": a, "normalized_context_end_exclusive": b,
            "source_pdf_fragments": fragments}


def ids_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode("utf-8")).hexdigest()


def user_prompt(primary, context, candidates):
    lines = ["目标引用覆盖的原文片段："]
    lines.extend(part["text"] for part in primary)
    if context:
        lines.append("必要上下文（仅用于解消指代）：")
        lines.extend(part["text"] for part in context)
    lines.append("候选证据：")
    lines.extend(f"{c['evidence_id']} | {c['model_text']}" for c in candidates)
    lines.append("仅对目标引用范围返回 label JSON；不能可靠判定时返回规定的 failure_status。")
    return "\n".join(lines)


def tokenize_prompt(tokenizer, user, system=SYSTEM_PROMPT):
    rendered = tokenizer.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                              tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"]
    return {"input_tokens": len(ids), "input_ids_sha256": ids_hash(ids), "rendered_prompt_sha256": gate.text_sha(rendered)}


def prepare(args):
    source, output = args.source_root.resolve(), args.output_dir.resolve()
    gate.require(not output.exists() and not output.is_relative_to(source) and not source.is_relative_to(output),
                 "Require a new output outside the immutable source package")
    recipe = gate.read_json(args.recipe)
    cases = gate.load_jsonl(source / "case_manifest.jsonl")
    recipes = gate.keyed(recipe["rows"], "case_id")
    gate.require(len(cases) == len(recipes) == 20 and {r["case_id"] for r in cases} == set(recipes), "Fixed 20-point set changed")
    pairs = gate.keyed(gate.load_jsonl(source / "pair_manifest.jsonl"), "pair_id")
    lock = gate.read_json(source / "scope_lock.json")
    for name, expected in lock["files_sha256"].items():
        gate.require(gate.sha(source / name) == expected, f"Source scope changed: {name}")
    for name, expected in TOKENIZER_FILES.items():
        gate.require(gate.sha(args.tokenizer_dir / name) == expected, f"Official pinned tokenizer file mismatch: {name}")
    os.environ.update(USE_TORCH="0", USE_TF="0", HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    sys.path.insert(0, str(args.tokenizer_deps.resolve()))
    sys.path.insert(0, str(args.bm25_deps.resolve()))
    import numpy
    import rank_bm25
    import transformers
    from transformers import AutoTokenizer
    import importlib.metadata
    gate.require(transformers.__version__ == "5.8.0" and importlib.metadata.version("rank-bm25") == "0.2.2", "Unpinned library versions")
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_dir, local_files_only=True)
    originals = gate.keyed(gate.load_jsonl(args.incoming_dir / "cited_evidence_results.jsonl"), "case_id")
    functions = original_functions(args.incoming_dir / "route1_pdf20_cited_retrieval_v1.py", source)
    pdf = gate.import_pdf(args.pymupdf_dir)
    replay = gate.PdfReplay(pdf)
    visual = gate.read_json(args.previous_review_dir / "visual_text_issue_case03_E02.json")
    gate.require(gate.sha(args.previous_review_dir / visual["review_image"]) == visual["review_image_sha256"], "Correction source image changed")
    raw_fragment = visual["pdf_fragments"][0]
    fixed_key = (visual["source_pdf_sha256"], raw_fragment["pdf_page"], raw_fragment["source_blocks"][0]["block_number"])
    original_text = raw_fragment["raw_text"]
    corrected = original_text
    patches = []
    for raw_form, replacement in (("50 end", "5′ end"), ("30 end", "3′ end")):
        gate.require(original_text.count(raw_form) == 1, "Correction is not uniquely scoped")
        index = original_text.index(raw_form) + 1
        patches.append({"within_block_index": index, "pdf_page_char_index": raw_fragment["char_start"] + index,
                        "before": "0", "after": "′", "raw_phrase": raw_form, "visible_pdf_phrase": replacement})
        corrected = corrected[:index] + "′" + corrected[index + 1:]
    gate.require(len(original_text) == len(corrected) and sum(a != b for a, b in zip(original_text, corrected)) == 2,
                 "Unexpected change outside the two visually confirmed prime glyphs")
    correction = {"patch_id": "trimmomatic_p03_prime_glyphs_v1", "source_pdf_sha256": fixed_key[0],
                  "pdf_page": fixed_key[1], "block_number": fixed_key[2], "raw_text": original_text,
                  "raw_text_sha256": gate.text_sha(original_text), "model_text": corrected,
                  "model_text_sha256": gate.text_sha(corrected), "patches": patches,
                  "visual_source_issue": str(args.previous_review_dir / "visual_text_issue_case03_E02.json"),
                  "visual_source_image_sha256": visual["review_image_sha256"],
                  "review_type": "assistant visually checked source normalization; not two-person adjudication",
                  "original_pdf_and_cache_edited": False}
    output.mkdir(parents=True)
    policy = {"created_before_new_retrieval_at_utc": datetime.now(timezone.utc).isoformat(),
              "stage": "v3_input_preparation_draft_no_model_run", "case_count": 20,
              "source_scope_files_sha256": lock["files_sha256"], "recipe_sha256": gate.sha(args.recipe),
              "retrieval": {"engine": "rank_bm25.BM25Okapi", "version": "0.2.2", "k1": 1.2, "b": .75,
                            "top_k": 10, "filter": "unchanged received v1 filter", "query": "source-mapped scope recipe",
                            "index_text": "raw source block except the separately logged two prime-glyph corrections"},
              "input_budget": {"max_length": 5120, "max_new_tokens": 512, "truncation": False,
                               "all_ten_candidates_retained": True, "overflow_policy": "hold, never silently drop a point or crop evidence"},
              "classifier": {"name": "Mbio", "checkpoint": "checkpoint-100", "adapter_sha256": cases[0]["classifier_preselected"]["adapter_sha256_expected"],
                             "base_revision": BASE_REVISION, "enable_thinking": False, "do_sample": False},
              "prompt_version": PROMPT_VERSION, "system_prompt_sha256": gate.text_sha(SYSTEM_PROMPT),
              "scope_holds": [r["case_id"] for r in recipe["rows"] if r.get("hold")],
              "human_joint_signoff": False, "GPU_or_model_execution": False}
    gate.write_json(output / "preparation_policy_before_cpu_retrieval.json", policy)
    gate.write_json(output / "text_layer_corrections.json", correction)
    control_inputs = gate.load_jsonl(args.control_inputs)
    control_predictions = gate.keyed(gate.load_jsonl(args.control_predictions), "candidate_id")
    controls = []
    for record in control_inputs:
        result = tokenize_prompt(tokenizer, record["user_prompt"], record["system_prompt"])
        prior = control_predictions[record["claim_id"]]
        gate.require(result["input_tokens"] == prior["input_tokens"] and record["input_sha256"] == prior["input_sha256"],
                     "Official local tokenizer disagrees with known A100 control")
        controls.append({"claim_id": record["claim_id"], "local_input_tokens": result["input_tokens"],
                         "prior_A100_input_tokens": prior["input_tokens"], "input_sha256": record["input_sha256"]})
    reviews, retrieved, drafts, budget_rows, caches = [], [], [], [], {}
    try:
        for number, case in enumerate(cases, 1):
            rule = recipes[case["case_id"]]
            pair = pairs[case["pair_id"]]
            citing = replay.open(source, pair["citing"])
            cited = replay.open(source, pair["cited"])
            for item in (pair["citing"], pair["cited"]):
                if item["sha256"] not in caches:
                    caches[item["sha256"]] = gate.load_jsonl(source / "pdf_text" / item["sha256"] / "blocks.jsonl")
            normalized, mapping = normalized_with_map(case["citing_context_raw_fragments"])
            gate.require(normalized == case["citing_context"], f"Context normalization mismatch: {case['case_id']}")
            primary = [located_piece(case, item, mapping, caches[pair["citing"]["sha256"]], replay, citing) for item in rule["primary"]]
            context = [located_piece(case, item, mapping, caches[pair["citing"]["sha256"]], replay, citing) for item in rule["context"]]
            primary_fragments = [f for part in primary for f in part["source_pdf_fragments"]]
            gate.require(all(gate.marker_inside(marker, primary_fragments) for marker in case["citation_marker_locator"]),
                         "Physical target reference marker outside proposed primary scope")
            query = case["target_claim_scope_proposal"] if rule.get("keep_original_query") else "\n".join(p["text"] for p in context + primary)
            review = {"case_id": case["case_id"], "pair_id": case["pair_id"], "dedup_key": case["dedup_key"],
                      "source_pool_candidate_id": case["source_pool_candidate_id"], "target_reference_id": case["reference_id"],
                      "original_full_context_marked": case["citing_context_marked"],
                      "old_scope_query": case["target_claim_scope_proposal"], "primary_scope_pieces": primary,
                      "context_only_pieces": context, "prepared_query": query,
                      "query_changed": query != case["target_claim_scope_proposal"], "boundary_reason": rule["reason"],
                      "scope_status": rule.get("hold") or "assistant_source_boundary_checked",
                      "reviewer_signoff": {"李云": None, "陈明进": None},
                      "exposure": {"prior_retrieval_known": True, "new_model_predictions_seen": False, "independent_blind_claimed": False},
                      "label": None, "joint_adjudication": None}
            reviews.append(review)
            blocks, short, ref = functions["load_blocks"](pair["cited"]["sha256"])
            index_texts = [corrected if (pair["cited"]["sha256"], b["pdf_page"], b["block_number"]) == fixed_key else b["raw_text"] for b in blocks]
            bm25 = rank_bm25.BM25Okapi([functions["tokenize"](text) for text in index_texts], k1=1.2, b=.75)
            scores = bm25.get_scores(functions["tokenize"](query))
            selected = sorted(range(len(blocks)), key=lambda i: scores[i], reverse=True)[:10]
            candidates = []
            for rank, index in enumerate(selected, 1):
                block = blocks[index]
                fragment = {key: block[key] for key in ("pdf_page", "char_start", "char_end_exclusive", "raw_text", "raw_text_sha256")}
                fragment.update(printed_page=None, source_blocks=[{"block_number": block["block_number"], "bbox": block["bbox"]}],
                                offset_basis=gate.OFFSET_BASIS, bbox_scope=gate.BBOX_SCOPE)
                replay.fragment(cited, fragment)
                applied = (pair["cited"]["sha256"], block["pdf_page"], block["block_number"]) == fixed_key
                model_text = index_texts[index]
                gate.require((model_text == block["raw_text"]) or applied, "Unlogged evidence rewrite")
                candidates.append({"evidence_id": f"D01:S{rank:02d}", "retrieval_rank": rank,
                                   "retrieval_score": round(float(scores[index]), 6),
                                   "source_block_id": f"{pair['cited']['sha256']}:P{block['pdf_page']}:B{block['block_number']}",
                                   "source_pdf_sha256": pair["cited"]["sha256"], "pdf_fragments": [fragment],
                                   "raw_text": block["raw_text"], "raw_text_sha256": block["raw_text_sha256"],
                                   "model_text": model_text, "model_text_sha256": gate.text_sha(model_text),
                                   "correction_patch_ids": [correction["patch_id"]] if applied else []})
            gate.require(len(candidates) == 10, "Never reduce the declared top ten silently")
            entry = {"case_id": case["case_id"], "pair_id": case["pair_id"], "query": query,
                     "stage": "local_CPU_scope_query_and_text_correction_preparation_v2", "operator": "李云侧辅助准备",
                     "candidate_pool_size": len(blocks), "filtered_short": short, "filtered_reference": ref,
                     "candidates": candidates, "original_v1_candidates_preserved": True}
            retrieved.append(entry)
            user = user_prompt(primary, context, candidates)
            tokens = tokenize_prompt(tokenizer, user)
            within = tokens["input_tokens"] + 512 <= 5120
            budget = {"case_id": case["case_id"], **tokens, "max_new_tokens": 512,
                      "required_total": tokens["input_tokens"] + 512, "max_length": 5120,
                      "within_budget": within, "candidate_count": 10, "truncation": False,
                      "scope_hold": rule.get("hold"), "draft_only": True}
            budget_rows.append(budget)
            drafts.append({"claim_id": case["case_id"], "system_prompt": SYSTEM_PROMPT, "user_prompt": user,
                           "input_sha256": gate.model_input_sha256(SYSTEM_PROMPT, user),
                           "prompt_version": PROMPT_VERSION, "source_case_id": case["case_id"],
                           "stage": "draft_input_not_released_for_model_execution", "scope_hold": rule.get("hold"),
                           "within_budget": within, "model_run_performed": False, "expected_input_ids_sha256": tokens["input_ids_sha256"]})
            print(f"[{number:02d}/20] scope={review['scope_status']} tokens={tokens['input_tokens']}+512 budget_ok={within}", flush=True)
    finally:
        replay.close()
    # Scientific-content guardrails are about the source target, not a label.
    by_id = {r["case_id"]: r for r in reviews}
    gate.require("100,000" in by_id[cases[1]["case_id"]]["primary_scope_pieces"][0]["text"], "Lost quantity qualifier")
    gate.require("40-fold" in by_id[cases[13]["case_id"]]["primary_scope_pieces"][0]["text"], "Lost numerical target")
    gate.require("nasal and pharyngeal" in by_id[cases[15]["case_id"]]["primary_scope_pieces"][0]["text"], "Lost specimen condition")
    gate.require("81,109" not in by_id[cases[11]["case_id"]]["prepared_query"], "Unrelated global-count claim leaked into case12")
    gate.require("1.4%" not in by_id[cases[19]["case_id"]]["prepared_query"], "Different physical citation occurrence leaked into case20")
    gate.write_jsonl(output / "scope_review.jsonl", reviews)
    gate.write_jsonl(output / "retrieval_v2_preparation.jsonl", retrieved)
    gate.write_jsonl(output / "classification.draft.inputs.jsonl", drafts)
    gate.write_json(output / "input_budget_report.json", {"rows": budget_rows, "maximum_required_total": max(r["required_total"] for r in budget_rows),
                                                          "over_budget_cases": [r["case_id"] for r in budget_rows if not r["within_budget"]]})
    gate.write_json(output / "tokenizer_provenance.json", {"repository": "Qwen/Qwen3.8-27B", "revision": BASE_REVISION,
              "verified_official_file_hashes": TOKENIZER_FILES, "local_snapshot": str(args.tokenizer_dir),
              "transformers": transformers.__version__, "tokenizers": importlib.metadata.version("tokenizers"),
              "numpy": numpy.__version__, "python": platform.python_version(), "prior_A100_controls": controls,
              "control_inputs_sha256": gate.sha(args.control_inputs), "control_predictions_sha256": gate.sha(args.control_predictions),
              "token_hash_basis": "SHA-256 of compact JSON UTF-8 array of actual input token IDs, not character estimates"})
    for name, expected in lock["files_sha256"].items():
        gate.require(gate.sha(source / name) == expected, "Immutable source changed during preparation")
    gate.require(len(drafts) == len(reviews) == len(retrieved) == 20, "Fixed denominator changed")
    summary = {"stage": "local_scope_correction_and_input_preparation_only", "case_count": 20,
               "script_sha256": gate.sha(Path(__file__)), "recipe_sha256": gate.sha(args.recipe),
               "recipe_version": recipe["version"], "physical_points_or_pairs_changed": False,
               "assistant_boundary_checked": sum(not r.get("hold") for r in recipe["rows"]),
               "scope_confirmation_holds": [{"case_id": r["case_id"], "reason": r["hold"]} for r in recipe["rows"] if r.get("hold")],
               "query_changed_points": sum(r["query_changed"] for r in reviews),
               "correction_patch_count": 1, "corrected_characters": 2,
               "CPU_retrieval_preparation_cases": 20, "candidates": sum(len(r["candidates"]) for r in retrieved),
               "model_input_drafts": 20, "all_ten_candidates_kept_per_point": True,
               "within_5120_including_512_generation": sum(r["within_budget"] for r in budget_rows),
               "maximum_required_total": max(r["required_total"] for r in budget_rows),
               "no_silent_truncation": True, "formal_v3_input_release": False,
               "model_runs": 0, "human_labels_written": 0, "joint_adjudications": 0,
               "engineering_accepted": 0, "formal_location_denominator": 20, "formal_location_rate": None,
               "generated_files_sha256": {p.name: gate.sha(p) for p in sorted(output.iterdir()) if p.is_file()}}
    gate.write_json(output / "preparation_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("source-root", "incoming-dir", "previous-review-dir", "output-dir", "recipe", "tokenizer-dir",
                 "tokenizer-deps", "bm25-deps", "pymupdf-dir", "control-inputs", "control-predictions"):
        p.add_argument("--" + name, type=Path, required=True)
    prepare(p.parse_args())


if __name__ == "__main__":
    main()
