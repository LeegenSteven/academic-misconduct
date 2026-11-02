"""Versioned scope-map loader for the unreleased remaining-13 CPU draft.

Reuse the original classifier, explainer, decoding, release checks and backend.
Only source-piece validation and CPU preparation accept the new origin maps.
No release or human confirmation is inferred by this entry point.
"""
from __future__ import annotations

import copy
from pathlib import Path
import re
import unicodedata

import run_route1_pdf_v3 as gate
import prepare_pdf20_scope_inputs_20261020 as prep
import route1_pdf_pipeline_v3 as base

VERSION = "route1_pdf_remaining13_runtime_20261024"
DRAFT_VERSION = "route1_pdf_remaining13_source_revision_draft_20261024"
ORIGINAL_RUNTIME_SHA256 = "80d17ad57db84c218ac3b0046432f12cbd915835003576ccf3fc5f6571faf055"
PRIME_SHA256 = "1cbeb0c6eef02dc4e7b7861eb22e43a0188e278d2b635ef8ea3e99f75df2b547"
ALLOWED_PATCHES = {
    "p07_transmission_wrap": ("1b9f4a28378fdb4bd1b47cd2c3c0d191f82735bf4c2ecf13ffb6ceefc6fd70fa", 2, 3726, "trans\u00ad\nmission", "transmission", [5, 6]),
    "p12_SARS_lexical_hyphen": ("1a8ff3e9322ce66224a2dd582930b4755e049fb5e39d3b17e06aacd879dae4c3", 2, 859, "SARS-\nCoV", "SARS-CoV", [5]),
    "p16_high_throughput_lexical_hyphen": ("1a8ff3e9322ce66224a2dd582930b4755e049fb5e39d3b17e06aacd879dae4c3", 2, 2214, "high-\nthroughput", "high-throughput", [5]),
}
_old_code_hashes = base.code_hashes


def mapped_source(fragments, pdf_sha, patches):
    chars, origins, used = [], [], []
    for fi, fragment in enumerate(fragments):
        if fi:
            chars.append("\n"); origins.append(None)
        skip = set()
        for patch in patches:
            if (patch["source_pdf_sha256"], patch["pdf_page"]) != (pdf_sha, fragment["pdf_page"]):
                continue
            if not (fragment["char_start"] <= patch["start"] and patch["end"] <= fragment["char_end_exclusive"]):
                continue
            index = patch["start"] - fragment["char_start"]
            gate.require(fragment["raw_text"][index:index + len(patch["raw"])] == patch["raw"], "Patch source differs")
            skip.update(patch["start"] + i for i in patch["skip_relative"])
            used.append(patch["patch_id"])
        for offset, raw_char in enumerate(fragment["raw_text"]):
            absolute = fragment["char_start"] + offset
            if absolute not in skip:
                for char in unicodedata.normalize("NFKC", raw_char):
                    if char != "\u00ad":
                        chars.append(char); origins.append([fi, absolute])
    deleted = set()
    for match in re.finditer(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "".join(chars)):
        deleted.update(range(match.start(), match.end()))
    text, mapping = [], []
    for index, (char, origin) in enumerate(zip(chars, origins)):
        if index in deleted:
            continue
        if char.isspace():
            if text and text[-1] != " ":
                text.append(" "); mapping.append(origin)
        else:
            text.append(char); mapping.append(origin)
    if text and text[-1] == " ":
        text.pop(); mapping.pop()
    return "".join(text), mapping, used


def verify_revised_part(part, pdf_sha, patches):
    gate.require(part["normalization_version"] == DRAFT_VERSION, "Unknown source map version")
    gate.require("normalized_context_start" not in part and "normalized_context_end_exclusive" not in part,
                 "Changed source text cannot retain active old normalized offsets")
    text, origins, used = mapped_source(part["source_pdf_fragments"], pdf_sha, patches)
    gate.require(text == part["text"], "Revised text differs from explicit source normalization")
    gate.require(origins == part["source_char_origin_map"] and len(origins) == len(text), "Revised character origins differ")
    gate.require(used == part["applied_source_patch_ids"], "Undeclared source patch")


def load_prepared(source, prepared, pdf):
    source, prepared = Path(source).resolve(), Path(prepared).resolve()
    summary = gate.read_json(prepared / "summary.json")
    gate.require(summary["version"] == DRAFT_VERSION and summary["new_model_runs"] == 0, "Wrong draft version")
    hashes = {"summary.json": gate.sha(prepared / "summary.json")}
    for filename, expected in summary["generated_files_sha256"].items():
        gate.require(gate.sha(gate.relative_file(prepared, filename)) == expected, f"Draft changed: {filename}")
        hashes[filename] = expected
    policy = gate.read_json(prepared / "policy_before_cpu_retrieval.json")
    for filename, expected in policy["source_scope_files_sha256"].items():
        gate.require(gate.sha(gate.relative_file(source, filename)) == expected, "Source scope files changed")
    patches = policy["source_transcription_patches"]
    gate.require(len(patches) == len(ALLOWED_PATCHES) and {p["patch_id"] for p in patches} == set(ALLOWED_PATCHES), "Wrong patch set")
    for patch in patches:
        actual = (patch["source_pdf_sha256"], patch["pdf_page"], patch["start"], patch["raw"], patch["model"], patch["skip_relative"])
        gate.require(actual == ALLOWED_PATCHES[patch["patch_id"]] and patch["end"] == patch["start"] + len(patch["raw"]), "Patch exceeds reviewed source location")
    correction_path = prepared / "runtime_adapter/text_layer_corrections.json"
    gate.require(gate.sha(correction_path) == PRIME_SHA256, "Existing prime correction changed")
    hashes["runtime_adapter/text_layer_corrections.json"] = PRIME_SHA256
    correction = gate.read_json(correction_path)
    cases = gate.load_jsonl(source / "case_manifest.jsonl")
    pairs = gate.keyed(gate.load_jsonl(source / "pair_manifest.jsonl"), "pair_id")
    scopes = gate.load_jsonl(prepared / "scope_review.draft.jsonl")
    retrieval = gate.load_jsonl(prepared / "retrieval.draft.jsonl")
    classifiers = gate.load_jsonl(prepared / "classification.draft.inputs.jsonl")
    explanations = gate.load_jsonl(prepared / "explanation.draft.inputs.jsonl")
    gate.require(len(cases) == len(scopes) == len(retrieval) == len(classifiers) == len(explanations) == 20, "Fixed denominator changed")
    gate.require(len({c["dedup_key"] for c in cases}) == len({c["case_id"] for c in cases}) == 20, "Duplicate physical point")
    replay, items = gate.PdfReplay(pdf), []
    try:
        for case, scope, retrieved, classifier, explainer in zip(cases, scopes, retrieval, classifiers, explanations):
            cid = case["case_id"]
            gate.require(cid == scope["case_id"] == retrieved["case_id"] == classifier["claim_id"] == explainer["claim_id"], "Point order differs")
            gate.require(case["pair_id"] == scope["pair_id"] == retrieved["pair_id"] and case["dedup_key"] == scope["dedup_key"], "Pair/point mismatch")
            gate.require(case["domain"] == "biomedicine" and case["classifier_preselected"]["name"] == "Mbio"
                         and case["classifier_preselected"]["checkpoint"] == "checkpoint-100"
                         and case["classifier_preselected"]["adapter_sha256_expected"] == base.ADAPTER_SHA, "Model preselection changed")
            pair = pairs[case["pair_id"]]
            citing, cited = replay.open(source, pair["citing"]), replay.open(source, pair["cited"])
            for fragment in case["reference_pdf_title_locator"] + case["citation_marker_locator"]:
                replay.fragment(citing, fragment)
            gate.require(scope["original_full_context_marked"] == case["citing_context_marked"], "Original context changed")
            primary = []
            for key in ("primary_scope_pieces", "context_only_pieces"):
                for part in scope[key]:
                    for fragment in part["source_pdf_fragments"]:
                        replay.fragment(citing, fragment)
                    if part.get("normalization_version"):
                        verify_revised_part(part, pair["citing"]["sha256"], patches)
                    else:
                        gate.require(case["citing_context"][part["normalized_context_start"]:part["normalized_context_end_exclusive"]] == part["text"], "Original scope differs")
                    if key == "primary_scope_pieces":
                        primary.extend(part["source_pdf_fragments"])
            gate.require(all(gate.marker_inside(marker, primary) for marker in case["citation_marker_locator"]), "Target marker outside primary scope")
            candidates = retrieved["candidates"]
            gate.require(len(candidates) == 10 and retrieved["query"] == scope["prepared_query"], "Query/candidates differ")
            for rank, evidence in enumerate(candidates, 1):
                gate.require(evidence["source_pdf_sha256"] == pair["cited"]["sha256"] and evidence["retrieval_rank"] == rank
                             and evidence["evidence_id"] == f"D01:S{rank:02d}" and len(evidence["pdf_fragments"]) == 1, "Evidence identity/rank differs")
                fragment = evidence["pdf_fragments"][0]
                replay.fragment(cited, fragment)
                gate.require(evidence["raw_text"] == fragment["raw_text"] and gate.text_sha(evidence["raw_text"]) == evidence["raw_text_sha256"]
                             and gate.text_sha(evidence["model_text"]) == evidence["model_text_sha256"], "Evidence text/hash differs")
                if evidence["correction_patch_ids"]:
                    gate.require(evidence["correction_patch_ids"] == [correction["patch_id"]]
                                 and evidence["source_pdf_sha256"] == correction["source_pdf_sha256"] and fragment["pdf_page"] == correction["pdf_page"]
                                 and fragment["source_blocks"][0]["block_number"] == correction["block_number"]
                                 and evidence["raw_text"] == correction["raw_text"] and evidence["model_text"] == correction["model_text"], "Prime patch moved")
                else:
                    gate.require(evidence["raw_text"] == evidence["model_text"], "Unlogged evidence rewrite")
            user = prep.user_prompt(scope["primary_scope_pieces"], scope["context_only_pieces"], candidates)
            gate.require(classifier["system_prompt"] == prep.SYSTEM_PROMPT and classifier["user_prompt"] == user
                         and classifier["input_sha256"] == gate.model_input_sha256(prep.SYSTEM_PROMPT, user), "Classifier payload changed")
            exp_user = user.rsplit("\n仅对目标引用范围返回 label JSON；不能可靠判定时返回规定的 failure_status。", 1)[0] + "\n仅返回规定的证据摘录和解释 JSON，不输出分类标签。"
            gate.require(explainer["system_prompt"] == base.EXPLANATION_SYSTEM and explainer["user_prompt"] == exp_user
                         and explainer["input_sha256"] == gate.model_input_sha256(base.EXPLANATION_SYSTEM, exp_user), "Explainer payload changed")
            scope_hash = base.digest({k: scope[k] for k in ("case_id", "pair_id", "dedup_key", "primary_scope_pieces", "context_only_pieces")})
            items.append({"case": case, "pair": pair, "scope": scope, "scope_sha256": scope_hash,
                          "retrieval": retrieved, "classifier": classifier, "explainer": explainer})
    finally:
        replay.close()
    return items, hashes


def code_hashes():
    hashes = _old_code_hashes()
    hashes[Path(__file__).name] = gate.sha(__file__)
    return hashes


def prepare_runtime(source, prepared, output, pdf, tokenizer):
    items, hashes = load_prepared(source, prepared, pdf)
    output = base.new_directory(output, source, prepared)
    rows, confirmations = [], []
    for item in items:
        stages = {name: {"input_sha256": item[name]["input_sha256"], **base.budget(tokenizer, item[name])} for name in ("classifier", "explainer")}
        gate.require(stages["classifier"]["input_ids_sha256"] == item["classifier"]["expected_input_ids_sha256"], "Draft classifier tokens changed")
        gate.require(all(x["within_budget"] for x in stages.values()), "Budget overflow")
        cid = item["case"]["case_id"]
        rows.append({"case_id": cid, "pair_id": item["case"]["pair_id"], "scope_sha256": item["scope_sha256"],
                     "scope_hold": item["classifier"]["scope_hold"], "stages": stages, "released": False})
        confirmations.append({"case_id": cid, "scope_sha256": item["scope_sha256"], "confirmed": False, "reviewer": None,
                              "reviewed_at": None, "review_source": None, "hold_resolution": None,
                              "note": "Actual scope confirmation required; not a label or acceptance signature"})
    policy = gate.read_json(Path(prepared) / "policy_before_cpu_retrieval.json")
    plan = {"version": VERSION, "created_at_utc": base.now(), "kind": "CPU_preparation_not_a_release", "prepared_files_sha256": hashes,
            "source_files_sha256": policy["source_scope_files_sha256"], "code_sha256": code_hashes(), "code_repository": gate.code_provenance(),
            "fixed_denominator": 20, "rows": rows,
            "classifier_model": {"base": "Qwen/Qwen3.8-27B", "revision": prep.BASE_REVISION, "adapter": "Mbio/checkpoint-100", "adapter_sha256": base.ADAPTER_SHA},
            "explanation_model": {"base": "Qwen/Qwen3.8-27B", "revision": prep.BASE_REVISION, "adapter": None, "role": "independent_official_base_explainer"},
            "settings": {"max_length": 5120, "max_new_tokens": 512, "enable_thinking": False, "do_sample": False, "retry_policy": "none; keep all first attempts"},
            "frozen": False, "model_loaded": False, "GPU_used": False, "human_labels_written": 0}
    base.write_json(output / "runtime_plan.json", plan)
    base.write_json(output / "scope_confirmation_template.json", {"version": VERSION, "runtime_plan_sha256": gate.sha(output / "runtime_plan.json"), "rows": confirmations})
    base.write_json(output / "CPU_check_summary.json", {"version": VERSION, "fixed_points": 20, "source_candidates_replayed": 200,
                    "stages_checked": 40, "all_within_budget": True, "released": 0, "model_runs": 0, "maximum_required_tokens": max(v["required_total"] for r in rows for v in r["stages"].values())})
    return plan


def install():
    gate.require(gate.sha(base.__file__) == ORIGINAL_RUNTIME_SHA256, "Original runtime version changed; review adapter again")
    base.VERSION = VERSION
    base.load_prepared = load_prepared
    base.prepare_runtime = prepare_runtime
    base.code_hashes = code_hashes


if __name__ == "__main__":
    install()
    raise SystemExit(base.main())
