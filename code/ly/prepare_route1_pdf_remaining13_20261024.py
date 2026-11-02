"""Prepare an unreleased, source-mapped revision of the remaining 13 PDF points.

CPU retrieval and official-tokenizer budgets only. Existing data, first responses,
scope releases, human labels and acceptance records are never modified. This is
not a replacement for the original runtime's scope validation or a GPU release.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

VERSION = "route1_pdf_remaining13_source_revision_draft_20261024"
SELECTED = (7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20)
NOTES = {
    7: "保留复合主张；仅将已定位跨行trans mission恢复为transmission。",
    8: "将已有母句谓语移入目标范围，保留connectivity的指代背景；不核查同句其他方法。",
    9: "保留现范围；X是未来可能加入的类别，不预指定已验证的新标志物。",
    10: "保留rare及A−T2+范围；原候选覆盖和图注不一致继续待核，不人工挑选替代候选。",
    11: "补入This bioinformatics approach的前句指代背景，主范围不变。",
    12: "只恢复已定位的SARS-CoV词内连字符，保留原严重程度限定。",
    13: "主范围不变；加入biomarker profile与clinical staging的区别作为背景。",
    14: "主范围不变；补足痴呆终点、参考组及原数值背景，不替换施引数值。",
    16: "只恢复已定位high-throughput的词内连字符；病例定义与引用归属仍需分别核对。",
    17: "保留六级临床分期的原范围，不与生物分组混同。",
    18: "保留临床特征类似的范围及引用归属，不扩展为疾病完全相同或死亡率判断。",
    19: "保留(N)相对A/T的特异性比较，不混入后续取消括号的修订。",
    20: "保留common及some cases severe两个限定，不由频率句代替严重程度依据。",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    workspace, output = args.workspace.resolve(), args.output_dir.resolve()
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_route1_pdf_v3 as gate
    import prepare_pdf20_scope_inputs_20261020 as prep
    import route1_pdf_pipeline_v3 as runtime
    from replay_cmj_pdf20_retrieval_20261020 import original_functions

    demo = repo / "results/route1_qwen38_v3/2026-10-25/pdf_demo"
    old = demo / "scope_and_input_preparation_2026-10-20"
    source = workspace / "10.19-11.2/路线一PDF独立清单_20261020"
    tokenizer_dir = workspace / "tmp/pdf20_official_tokenizer_snapshot_20261020"
    deps = workspace / "tmp/pdf20_tokenizer_deps_20261020"
    gate.require(not output.exists(), "Use a new output directory")
    gate.require(not output.is_relative_to(source) and not output.is_relative_to(old), "Immutable source/preparation output forbidden")
    os.environ.update(USE_TORCH="0", USE_TF="0", HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false", CUDA_VISIBLE_DEVICES="")
    sys.path.insert(0, str(deps))
    sys.path.insert(0, str(workspace / "tmp/pdf20_bm25_replay_deps_20261020"))
    import rank_bm25
    gate.require(importlib.metadata.version("rank-bm25") == "0.2.2", "Unpinned BM25 version")
    pdf = gate.import_pdf(workspace / "tmp/pdf_locator_deps")
    tokenizer = runtime.tokenizer_for(tokenizer_dir, deps)
    old_items, old_integrity = runtime.load_prepared(source, old, pdf)
    old_by_id = {x["case"]["case_id"]: x for x in old_items}
    cases = gate.load_jsonl(source / "case_manifest.jsonl")
    pairs = gate.keyed(gate.load_jsonl(source / "pair_manifest.jsonl"), "pair_id")
    gate.require(len(cases) == len(old_items) == 20, "Fixed point set changed")
    rows = gate.load_jsonl(demo / "readiness_2026-10-23/source_diagnostics.jsonl")
    diagnostic = {x["key"]: x for x in rows}
    protected = {str(old / n): h for n, h in old_integrity.items()}
    lock = gate.read_json(source / "scope_lock.json")
    protected.update({str(source / n): h for n, h in lock["files_sha256"].items()})
    for pair in pairs.values():
        for role in ("citing", "cited"):
            item = pair[role]
            protected[str(source / item["relative_path"])] = item["sha256"]
            cache = source / "pdf_text" / item["sha256"] / "blocks.jsonl"
            protected[str(cache)] = gate.sha(cache)
    first5 = workspace / "10.19-11.2/A100_PDF首批5点资源修订_20261022/route1_pdf_first5_20261022_resource_run01/assembled/records.jsonl"
    protected[str(first5)] = "495e96f319bc49d062460f14f9c23fccb62a18427c3ac0a0c1cab821a24fd2b5"
    for path, expected in protected.items():
        gate.require(gate.sha(path) == expected, f"Original changed: {path}")

    patches = [
        {"point_number": 7, "patch_id": "p07_transmission_wrap", "pdf_page": 2, "start": 3726,
         "raw": "trans\u00ad\nmission", "model": "transmission", "skip_relative": [5, 6]},
        {"point_number": 12, "patch_id": "p12_SARS_lexical_hyphen", "pdf_page": 2, "start": 859,
         "raw": "SARS-\nCoV", "model": "SARS-CoV", "skip_relative": [5]},
        {"point_number": 16, "patch_id": "p16_high_throughput_lexical_hyphen", "pdf_page": 2, "start": 2214,
         "raw": "high-\nthroughput", "model": "high-throughput", "skip_relative": [5]},
    ]
    for patch in patches:
        pair = pairs[cases[patch["point_number"] - 1]["pair_id"]]
        patch.update(source_pdf_sha256=pair["citing"]["sha256"], end=patch["start"] + len(patch["raw"]),
                     source_raw_sha256=gate.text_sha(patch["raw"]), model_text_sha256=gate.text_sha(patch["model"]),
                     human_confirmation=None, stage="draft_only_not_released")
        gate.require("".join(c for i, c in enumerate(patch["raw"]) if i not in patch["skip_relative"]) == patch["model"], "Patch inserts new content")
        gate.require(all(patch["raw"][i].isspace() or patch["raw"][i] == "\u00ad" for i in patch["skip_relative"]), "Patch deletes source words")

    def mapped_text(fragments, pdf_sha, apply_patches=True):
        chars, origins = [], []
        applied = []
        for fi, fragment in enumerate(fragments):
            if fi:
                chars.append("\n"); origins.append(None)
            relevant = [p for p in patches if p["source_pdf_sha256"] == pdf_sha and p["pdf_page"] == fragment["pdf_page"]
                        and fragment["char_start"] <= p["start"] and p["end"] <= fragment["char_end_exclusive"]] if apply_patches else []
            skips = set()
            for patch in relevant:
                a = patch["start"] - fragment["char_start"]
                gate.require(fragment["raw_text"][a:a + len(patch["raw"])] == patch["raw"], "Patch does not match raw location")
                skips.update(patch["start"] + i for i in patch["skip_relative"])
                applied.append(patch["patch_id"])
            for offset, char in enumerate(fragment["raw_text"]):
                absolute = fragment["char_start"] + offset
                if absolute in skips:
                    continue
                for value in unicodedata.normalize("NFKC", char):
                    if value != "\u00ad":
                        chars.append(value); origins.append([fi, absolute])
        text = "".join(chars)
        deleted = set()
        for match in re.finditer(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", text):
            deleted.update(range(match.start(), match.end()))
        result, mapping = [], []
        for i, (char, origin) in enumerate(zip(chars, origins)):
            if i in deleted:
                continue
            if char.isspace():
                if result and result[-1] != " ":
                    result.append(" "); mapping.append(origin)
            else:
                result.append(char); mapping.append(origin)
        if result and result[-1] == " ":
            result.pop(); mapping.pop()
        return "".join(result), mapping, applied

    def revise_part(part, pdf_sha):
        part = copy.deepcopy(part)
        old_text, _, _ = mapped_text(part["source_pdf_fragments"], pdf_sha, False)
        gate.require(old_text == part["text"], "Old source piece does not normalize to its recorded text")
        text, mapping, applied = mapped_text(part["source_pdf_fragments"], pdf_sha)
        part.update(text=text, original_normalized_text=old_text, source_char_origin_map=mapping,
                    normalization_version=VERSION, applied_source_patch_ids=applied)
        # Old normalized-context offsets describe the old context, never the revised text.
        part["original_normalized_context_span"] = [part.pop("normalized_context_start", None), part.pop("normalized_context_end_exclusive", None)]
        return part

    def part_from_fragment(fragment, pdf_sha):
        text, mapping, applied = mapped_text([fragment], pdf_sha)
        return {"text": text, "source_pdf_fragments": [copy.deepcopy(fragment)],
                "source_char_origin_map": mapping, "normalization_version": VERSION,
                "original_normalized_context_span": None, "applied_source_patch_ids": applied}

    replay = gate.PdfReplay(pdf)
    all_scopes, all_retrieval, classification, explanation, budgets, changes = [], [], [], [], [], []
    output.mkdir(parents=True)
    policy = {"version": VERSION, "created_before_cpu_retrieval_at_utc": datetime.now(timezone.utc).isoformat(),
              "stage": "draft_only_no_execution_release", "fixed_points": 20, "selected_remaining_points": list(SELECTED),
              "unchanged_first5_and_held_points": [1, 2, 3, 4, 5, 6, 15],
              "retrieval": {"engine": "BM25Okapi", "k1": 1.2, "b": .75, "top_k": 10,
                            "filter": "exact received v1 heuristic unchanged", "source_scope": "designated cited PDF only",
                            "query": "context-only pieces followed by primary pieces; unchanged points retain old query",
                            "index_text": "unchanged original preparation raw blocks and existing prime correction only"},
              "source_transcription_patches": patches, "new_candidate_text_corrections": 0,
              "source_scope_files_sha256": lock["files_sha256"], "classification_system_sha256": gate.text_sha(prep.SYSTEM_PROMPT),
              "explanation_system_sha256": gate.text_sha(runtime.EXPLANATION_SYSTEM),
              "max_length": 5120, "max_new_tokens": 512, "truncation": False,
              "new_human_labels": 0, "new_scope_confirmations": 0, "model_runs": 0,
              "changes_to_existing_runtime_or_release": False}
    gate.write_json(output / "policy_before_cpu_retrieval.json", policy)
    gate.write_json(output / "protected_original_files_sha256.json", protected)
    incoming = source / "2026-10-20_PDF20点被引检索/route1_pdf20_cited_retrieval_v1.py"
    functions = original_functions(incoming, source)
    correction = gate.read_json(old / "text_layer_corrections.json")
    try:
        for number, case in enumerate(cases, 1):
            item = old_by_id[case["case_id"]]
            scope = copy.deepcopy(item["scope"])
            old_scope = copy.deepcopy(scope)
            pair = pairs[case["pair_id"]]
            citing, cited = replay.open(source, pair["citing"]), replay.open(source, pair["cited"])
            new_scope = number in (7, 8, 11, 12, 13, 14, 16)
            if number == 8:
                proposal = gate.read_json(next(demo.glob("point08*")) / "母句归入目标范围建议_未应用.json")
                scope["primary_scope_pieces"] = proposal["proposed_primary_scope_pieces"]
                scope["context_only_pieces"] = proposal["proposed_context_only_pieces"]
            if number == 11:
                proposal = gate.read_json(next(demo.glob("point11*")) / "This指代上下文补充建议_未应用.json")
                scope["context_only_pieces"] = proposal["proposed_context_only_pieces"]
            if new_scope:
                for key in ("primary_scope_pieces", "context_only_pieces"):
                    scope[key] = [revise_part(part, pair["citing"]["sha256"]) for part in scope[key]]
            if number in (13, 14):
                key = "citing_profile_clarification" if number == 13 else "citing_dementia_endpoint_context"
                fragment = copy.deepcopy(diagnostic[key]["fragment"])
                if number == 14:
                    page = citing[fragment["pdf_page"] - 1]
                    raw_page = page.get_text("text", sort=False)
                    start = fragment["char_start"]
                    end = raw_page.index(".\n", fragment["char_end_exclusive"]) + 1
                    gate.require(end - fragment["char_end_exclusive"] < 8, "Unexpected sentence extension")
                    fragment.update(char_end_exclusive=end, raw_text=raw_page[start:end], raw_text_sha256=gate.text_sha(raw_page[start:end]))
                scope["context_only_pieces"].append(part_from_fragment(fragment, pair["citing"]["sha256"]))
            if new_scope:
                scope["prepared_query"] = "\n".join(p["text"] for p in scope["context_only_pieces"] + scope["primary_scope_pieces"])
                scope.update(scope_status="source_revision_draft_pending_scope_confirmation", boundary_reason=NOTES[number],
                             reviewer_signoff={"李云": None, "陈明进": None}, label=None, joint_adjudication=None)
            for key in ("primary_scope_pieces", "context_only_pieces"):
                for part in scope[key]:
                    for fragment in part["source_pdf_fragments"]:
                        replay.fragment(citing, fragment)
                    if new_scope:
                        text, mapping, _ = mapped_text(part["source_pdf_fragments"], pair["citing"]["sha256"])
                        gate.require(text == part["text"] and mapping == part["source_char_origin_map"], "Revised source map mismatch")
                        gate.require(len(mapping) == len(text), "Source map length differs")
            primary_fragments = [f for p in scope["primary_scope_pieces"] for f in p["source_pdf_fragments"]]
            gate.require(all(gate.marker_inside(m, primary_fragments) for m in case["citation_marker_locator"]), "Target marker left primary scope")
            retrieved = copy.deepcopy(item["retrieval"])
            if number in SELECTED:
                blocks, short, refs = functions["load_blocks"](pair["cited"]["sha256"])
                index_texts = [correction["model_text"] if (pair["cited"]["sha256"], b["pdf_page"], b["block_number"]) ==
                               (correction["source_pdf_sha256"], correction["pdf_page"], correction["block_number"]) else b["raw_text"] for b in blocks]
                bm25 = rank_bm25.BM25Okapi([functions["tokenize"](t) for t in index_texts], k1=1.2, b=.75)
                scores = bm25.get_scores(functions["tokenize"](scope["prepared_query"]))
                indices = sorted(range(len(blocks)), key=lambda i: scores[i], reverse=True)[:10]
                evidence = []
                for rank, index in enumerate(indices, 1):
                    block = blocks[index]
                    fragment = {k: block[k] for k in ("pdf_page", "char_start", "char_end_exclusive", "raw_text", "raw_text_sha256")}
                    fragment.update(printed_page=None, source_blocks=[{"block_number": block["block_number"], "bbox": block["bbox"]}],
                                    offset_basis=gate.OFFSET_BASIS, bbox_scope=gate.BBOX_SCOPE)
                    replay.fragment(cited, fragment)
                    patched = index_texts[index] != block["raw_text"]
                    evidence.append({"evidence_id": f"D01:S{rank:02d}", "retrieval_rank": rank, "retrieval_score": round(float(scores[index]), 6),
                                     "source_block_id": f"{pair['cited']['sha256']}:P{block['pdf_page']}:B{block['block_number']}",
                                     "source_pdf_sha256": pair["cited"]["sha256"], "pdf_fragments": [fragment],
                                     "raw_text": block["raw_text"], "raw_text_sha256": block["raw_text_sha256"],
                                     "model_text": index_texts[index], "model_text_sha256": gate.text_sha(index_texts[index]),
                                     "correction_patch_ids": [correction["patch_id"]] if patched else []})
                gate.require(len(evidence) == 10, "Wrong candidate count")
                retrieved.update(query=scope["prepared_query"], candidates=evidence, candidate_pool_size=len(blocks),
                                 filtered_short=short, filtered_reference=refs, stage=VERSION, operator="李云侧CPU准备；非人工签核")
                if scope["prepared_query"] == old_scope["prepared_query"]:
                    gate.require(evidence == item["retrieval"]["candidates"], "Unchanged query retrieval did not reproduce")
            user = prep.user_prompt(scope["primary_scope_pieces"], scope["context_only_pieces"], retrieved["candidates"])
            classifier = {"claim_id": case["case_id"], "system_prompt": prep.SYSTEM_PROMPT, "user_prompt": user,
                          "input_sha256": gate.model_input_sha256(prep.SYSTEM_PROMPT, user), "stage": "draft_input_not_released_for_model_execution",
                          "prompt_version": prep.PROMPT_VERSION, "scope_hold": item["classifier"]["scope_hold"], "model_run_performed": False}
            exp_user = user.rsplit("\n仅对目标引用范围返回 label JSON；不能可靠判定时返回规定的 failure_status。", 1)[0] + "\n仅返回规定的证据摘录和解释 JSON，不输出分类标签。"
            explainer = {"claim_id": case["case_id"], "system_prompt": runtime.EXPLANATION_SYSTEM, "user_prompt": exp_user,
                         "input_sha256": gate.model_input_sha256(runtime.EXPLANATION_SYSTEM, exp_user), "stage": "draft_only_no_model_run"}
            stages = {role: {"input_sha256": rec["input_sha256"], **runtime.budget(tokenizer, rec)} for role, rec in (("classifier", classifier), ("explainer", explainer))}
            classifier["expected_input_ids_sha256"] = stages["classifier"]["input_ids_sha256"]
            classifier["within_budget"] = stages["classifier"]["within_budget"]
            scope_hash = runtime.digest({k: scope[k] for k in ("case_id", "pair_id", "dedup_key", "primary_scope_pieces", "context_only_pieces")})
            budget = {"point_number": number, "case_id": case["case_id"], "scope_sha256": scope_hash,
                      "scope_hold": classifier["scope_hold"], "stages": stages, "released": False}
            if number in SELECTED:
                old_blocks = [c["source_block_id"] for c in item["retrieval"]["candidates"]]
                new_blocks = [c["source_block_id"] for c in retrieved["candidates"]]
                changes.append({"point_number": number, "case_id": case["case_id"], "pair_id": case["pair_id"],
                                "proposal": NOTES[number], "primary_before": [p["text"] for p in old_scope["primary_scope_pieces"]],
                                "primary_after": [p["text"] for p in scope["primary_scope_pieces"]],
                                "context_before": [p["text"] for p in old_scope["context_only_pieces"]],
                                "context_after": [p["text"] for p in scope["context_only_pieces"]],
                                "scope_changed": new_scope, "query_changed": retrieved["query"] != item["retrieval"]["query"],
                                "candidate_order_changed": old_blocks != new_blocks, "new_blocks_count": len(set(new_blocks) - set(old_blocks)),
                                "original_classifier_input_sha256": item["classifier"]["input_sha256"], "classifier_input_sha256": classifier["input_sha256"],
                                "classifier_input_changed": classifier["input_sha256"] != item["classifier"]["input_sha256"],
                                "classifier_required_tokens": stages["classifier"]["required_total"], "explainer_required_tokens": stages["explainer"]["required_total"],
                                "human_scope_confirmation": None, "human_label": None, "new_model_run": False})
            else:
                gate.require(scope == item["scope"] and retrieved == item["retrieval"], "First five/held record changed")
                gate.require(classifier["input_sha256"] == item["classifier"]["input_sha256"] and explainer["input_sha256"] == item["explainer"]["input_sha256"], "First five/held input changed")
            all_scopes.append(scope); all_retrieval.append(retrieved); classification.append(classifier); explanation.append(explainer); budgets.append(budget)
            print(f"POINT {number:02d} selected={number in SELECTED} draft_classifier_tokens={stages['classifier']['required_total']} draft_explainer_tokens={stages['explainer']['required_total']}", flush=True)
    finally:
        replay.close()
    gate.require(len(changes) == 13 and len(classification) == 20, "Fixed membership changed")
    gate.require(all(b["within_budget"] for x in budgets for b in x["stages"].values()), "Budget overflow; keep draft on hold")
    for path, expected in protected.items():
        gate.require(gate.sha(path) == expected, "Original changed during draft preparation")
    gate.write_jsonl(output / "scope_review.draft.jsonl", all_scopes)
    gate.write_jsonl(output / "retrieval.draft.jsonl", all_retrieval)
    gate.write_jsonl(output / "classification.draft.inputs.jsonl", classification)
    gate.write_jsonl(output / "explanation.draft.inputs.jsonl", explanation)
    gate.write_jsonl(output / "remaining13_changes.jsonl", changes)
    gate.write_json(output / "source_wrap_patches.draft.json", {"version": VERSION, "patches": patches})
    gate.write_json(output / "two_stage_budget_report.json", {"version": VERSION, "rows": budgets,
                    "note": "CPU budget evidence only; not an executable release or original-runtime-compatible preparation"})
    manifest = {p.name: gate.sha(p) for p in output.iterdir() if p.is_file()}
    summary = {"version": VERSION, "status": "CPU_DRAFT_PREPARATION_PASS_SCOPE_AND_RUNTIME_ADOPTION_PENDING",
               "client_date": "2026-10-24", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
               "fixed_points": 20, "remaining_points_prepared": 13, "candidate_count_per_point": 10,
               "selected_candidates_retrieved_and_PDF_replayed": 130,
               "source_wrap_patches": 3, "scope_or_text_revision_cases": sum(x["scope_changed"] for x in changes),
               "query_changed_cases": sum(x["query_changed"] for x in changes),
               "candidate_order_changed_cases": sum(x["candidate_order_changed"] for x in changes),
               "classifier_input_changed_cases": sum(x["classifier_input_changed"] for x in changes),
               "two_stage_budgets_checked": 40, "remaining13_stage_budgets_checked": 26,
               "maximum_required_tokens_remaining13": max(max(x["classifier_required_tokens"], x["explainer_required_tokens"]) for x in changes),
               "all_within_5120": True, "truncation": False, "original_first5_and_two_holds_input_hashes_unchanged": True,
               "actual_model_points_total_unchanged": 5, "formal_end_to_end_accepted_unchanged": 0,
               "unmodified_20261021_runtime_loader_compatible": False,
               "next_runtime_requirement": "Review and bind a versioned loader for the explicit source-origin maps; old normalized offsets must not be reused for changed text.",
               "human_labels_written": 0, "new_scope_confirmations": 0, "model_loaded": False, "GPU_used": False,
               "torch_imported": "torch" in sys.modules, "new_model_runs": 0,
               "source_script_sha256": gate.sha(__file__), "generated_files_sha256": manifest,
               "environment": {"python": sys.version.split()[0], "transformers": importlib.metadata.version("transformers"),
                               "tokenizers": importlib.metadata.version("tokenizers"), "rank_bm25": importlib.metadata.version("rank-bm25")}}
    gate.require(not summary["torch_imported"], "Unexpected torch import in tokenizer-only preparation")
    gate.write_json(output / "summary.json", summary)
    print("REMAINING13_CPU_DRAFT_PASS fixed=20 revised=7 retained=6 budgets=26 released=0 model_runs=0", flush=True)


if __name__ == "__main__":
    main()
