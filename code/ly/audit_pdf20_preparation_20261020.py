"""Audit the PDF20 preparation against immutable source files and actual PDFs.

Technical checks only; no model execution, human signoff or semantic acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

import run_route1_pdf_v3 as gate

SOURCE_ZIP_SHA = "6710893640734d072a50e284676b20c79bdc168d75f9db7940c5a72d9f06be9c"


def audit(args):
    src, prepared = args.source_root.resolve(), args.prepared_dir.resolve()
    gate.require(not args.output.exists(), "Keep earlier audit receipts; choose a new output")
    summary = gate.read_json(prepared / "preparation_summary.json")
    policy = gate.read_json(prepared / "preparation_policy_before_cpu_retrieval.json")
    for name, expected in summary["generated_files_sha256"].items():
        gate.require(gate.sha(prepared / name) == expected, f"Generated artifact changed: {name}")
    source_files = gate.read_json(src / "SHA256SUMS.json")["files"]
    for relative, meta in source_files.items():
        file = gate.relative_file(src, relative)
        gate.require(file.stat().st_size == meta["bytes"] and gate.sha(file) == meta["sha256"],
                     f"Immutable source file changed: {relative}")
    gate.require(gate.sha(args.source_zip) == SOURCE_ZIP_SHA, "Previously delivered ZIP changed")
    with zipfile.ZipFile(args.source_zip) as archive:
        entries = [f for f in archive.infolist() if not f.is_dir()]
        gate.require(len(entries) == len({f.filename for f in entries}) == len(source_files) + 1,
                     "Unexpected or repeated files in source ZIP")
        gate.require({f.filename for f in entries} == set(source_files) | {"SHA256SUMS.json"}, "Source ZIP set differs")
        for item in entries:
            gate.require(hashlib.sha256(archive.read(item)).hexdigest() == gate.sha(gate.relative_file(src, item.filename)),
                         f"Local source differs from delivered ZIP: {item.filename}")
    for name, expected in policy["source_scope_files_sha256"].items():
        gate.require(gate.sha(src / name) == expected, f"Source selection changed: {name}")
    prior_replay = gate.read_json(args.return_replay_summary)
    for name, expected in prior_replay["incoming_files_sha256"].items():
        gate.require(gate.sha(args.incoming_dir / name) == expected, f"Chen original return changed: {name}")
    cases = gate.load_jsonl(src / "case_manifest.jsonl")
    pairs = gate.keyed(gate.load_jsonl(src / "pair_manifest.jsonl"), "pair_id")
    scopes = gate.load_jsonl(prepared / "scope_review.jsonl")
    retrieval = gate.load_jsonl(prepared / "retrieval_v2_preparation.jsonl")
    inputs = gate.load_jsonl(prepared / "classification.draft.inputs.jsonl")
    budgets = gate.read_json(prepared / "input_budget_report.json")["rows"]
    token_receipt = gate.read_json(prepared / "independent_CPU_token_identity_check.json")
    gate.require(len(cases) == len(scopes) == len(retrieval) == len(inputs) == len(budgets) == 20, "Fixed denominator changed")
    for rows, key in ((scopes, "case_id"), (retrieval, "case_id"), (inputs, "claim_id"), (budgets, "case_id")):
        gate.require([r[key] for r in rows] == [r["case_id"] for r in cases], "Point ID/order changed")
    gate.require(len({r["dedup_key"] for r in cases}) == 20, "Duplicated physical point")
    gate.require(token_receipt["inputs_sha256"] == gate.sha(prepared / "classification.draft.inputs.jsonl")
                 and token_receipt["budget_report_sha256"] == gate.sha(prepared / "input_budget_report.json"), "Stale token receipt")
    checker = Path(__file__).with_name("check_pdf20_draft_token_ids_20261020.py")
    gate.require(token_receipt["checker_sha256"] == gate.sha(checker), "Token checker changed after run")
    gate.require(token_receipt["points"] == 20 and token_receipt["scope_holds"] == 2
                 and token_receipt["model_loaded"] is False and token_receipt["gpu_used"] is False
                 and token_receipt["formal_input_release"] is False, "Misstated token validation scope")
    corrections = gate.read_json(prepared / "text_layer_corrections.json")
    original, modified = corrections["raw_text"], corrections["model_text"]
    gate.require(len(original) == len(modified), "Unlogged length change")
    differences = [i for i, (a, b) in enumerate(zip(original, modified)) if a != b]
    gate.require(differences == [p["within_block_index"] for p in corrections["patches"]]
                 and len(differences) == 2, "Unlogged correction")
    gate.require(corrections["raw_text_sha256"] == gate.text_sha(original)
                 and corrections["model_text_sha256"] == gate.text_sha(modified), "Correction text hash mismatch")
    for patch in corrections["patches"]:
        at = patch["within_block_index"]
        gate.require(original[at] == patch["before"] == "0" and modified[at] == patch["after"] == "′", "Wrong glyph correction")
    image = prepared.parent / "cited_return_review_2026-10-20/qa/case03_E02_original_pdf_crop.png"
    gate.require(gate.sha(image) == corrections["visual_source_image_sha256"], "Visual correction basis changed")
    replay = gate.PdfReplay(gate.import_pdf(args.pymupdf_dir))
    scope_fragments = evidence_fragments = correction_uses = 0
    try:
        for case, review, retrieved, record, budget, token in zip(cases, scopes, retrieval, inputs, budgets, token_receipt["rows"]):
            pair = pairs[case["pair_id"]]
            gate.require(review["pair_id"] == retrieved["pair_id"] == case["pair_id"]
                         and review["dedup_key"] == case["dedup_key"], "Pair or physical marker changed")
            gate.require(review["original_full_context_marked"] == case["citing_context_marked"]
                         and review["target_reference_id"] == case["reference_id"], "Original context/reference changed")
            gate.require(review["label"] is None and review["joint_adjudication"] is None
                         and all(v is None for v in review["reviewer_signoff"].values()), "Fabricated human result")
            primary_fragments = []
            citing_doc = replay.open(src, pair["citing"])
            for section in ("primary_scope_pieces", "context_only_pieces"):
                for piece in review[section]:
                    start, end = piece["normalized_context_start"], piece["normalized_context_end_exclusive"]
                    gate.require(case["citing_context"][start:end] == piece["text"], "Scope text not from citing context")
                    for fragment in piece["source_pdf_fragments"]:
                        replay.fragment(citing_doc, fragment)
                        scope_fragments += 1
                        if section == "primary_scope_pieces":
                            primary_fragments.append(fragment)
            gate.require(all(gate.marker_inside(m, primary_fragments) for m in case["citation_marker_locator"]), "Target marker lost")
            gate.require(retrieved["query"] == review["prepared_query"] and len(retrieved["candidates"]) == 10, "Wrong retrieval inputs")
            cited_doc = replay.open(src, pair["cited"])
            model_lines = []
            for rank, candidate in enumerate(retrieved["candidates"], 1):
                gate.require(candidate["source_pdf_sha256"] == pair["cited"]["sha256"], "Cross-PDF evidence")
                gate.require(candidate["retrieval_rank"] == rank and candidate["evidence_id"] == f"D01:S{rank:02d}", "Wrong rank or ID")
                for fragment in candidate["pdf_fragments"]:
                    replay.fragment(cited_doc, fragment)
                    evidence_fragments += 1
                gate.require("".join(f["raw_text"] for f in candidate["pdf_fragments"]) == candidate["raw_text"], "Evidence assembly differs")
                gate.require(gate.text_sha(candidate["raw_text"]) == candidate["raw_text_sha256"]
                             and gate.text_sha(candidate["model_text"]) == candidate["model_text_sha256"], "Evidence hash mismatch")
                if candidate["correction_patch_ids"]:
                    expected_key = f"{corrections['source_pdf_sha256']}:P{corrections['pdf_page']}:B{corrections['block_number']}"
                    gate.require(candidate["source_block_id"] == expected_key
                                 and candidate["correction_patch_ids"] == [corrections["patch_id"]]
                                 and candidate["raw_text"] == original and candidate["model_text"] == modified, "Correction applied outside specified source block")
                    fragment = candidate["pdf_fragments"][0]
                    for patch in corrections["patches"]:
                        gate.require(fragment["char_start"] + patch["within_block_index"] == patch["pdf_page_char_index"], "Correction page offset mismatch")
                    correction_uses += 1
                else:
                    gate.require(candidate["model_text"] == candidate["raw_text"], "Unlogged evidence rewrite")
                model_lines.append(f"{candidate['evidence_id']} | {candidate['model_text']}")
            expected_user = ["目标引用覆盖的原文片段："] + [p["text"] for p in review["primary_scope_pieces"]]
            if review["context_only_pieces"]:
                expected_user += ["必要上下文（仅用于解消指代）："] + [p["text"] for p in review["context_only_pieces"]]
            expected_user += ["候选证据："] + model_lines + ["仅对目标引用范围返回 label JSON；不能可靠判定时返回规定的 failure_status。"]
            gate.require(record["user_prompt"] == "\n".join(expected_user), "Hidden fields or altered evidence in model payload")
            payload = {k: record[k] for k in ("system_prompt", "user_prompt")}
            payload_sha = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            gate.require(record["input_sha256"] == payload_sha and gate.text_sha(record["system_prompt"]) == policy["system_prompt_sha256"], "Prompt hash mismatch")
            gate.require(record["model_run_performed"] is False and "draft" in record["stage"], "Draft falsely released")
            gate.require(budget["candidate_count"] == 10 and budget["truncation"] is False and budget["within_budget"] is True
                         and budget["required_total"] == budget["input_tokens"] + 512 <= 5120, "Invalid budget")
            gate.require(token["case_id"] == case["case_id"] and token["input_ids_sha256"] == budget["input_ids_sha256"]
                         == record["expected_input_ids_sha256"] and token["input_tokens"] == budget["input_tokens"], "Token receipt mismatch")
    finally:
        replay.close()
    holds = [r["claim_id"] for r in inputs if r["scope_hold"]]
    gate.require(len(holds) == 2 and holds == policy["scope_holds"] and correction_uses == 1, "Hold/patch counts differ")
    gate.require(sum(r["query_changed"] for r in scopes) == summary["query_changed_points"] == 9, "Changed-query count differs")
    gate.require(summary["formal_v3_input_release"] is False and summary["model_runs"] == 0
                 and summary["formal_location_rate"] is None and summary["formal_location_denominator"] == 20, "Preparation mislabeled as final acceptance")
    link_count = 0
    for doc in (prepared / "README.md", prepared / "20点范围与输入逐条查看.md", prepared.parent / "README.md"):
        for link in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
            if re.match(r"\w+://", link) or link.startswith("#"):
                continue
            path = (doc.parent / link.split("#", 1)[0].strip("<>")).resolve()
            if path == args.output.resolve():
                continue
            gate.require(path.exists(), f"Broken local document link: {doc.name}: {link}")
            link_count += 1
    report = {
        "status": "passed_preparation_integrity_and_actual_PDF_replay_only", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_script_sha256": gate.sha(Path(__file__)), "source_files_unchanged": len(source_files), "source_zip_files_equal": len(entries),
        "source_zip_sha256": SOURCE_ZIP_SHA, "Chen_original_return_files_unchanged": len(prior_replay["incoming_files_sha256"]),
        "fixed_points": 20, "fixed_pairs": len({r["pair_id"] for r in cases}), "actual_PDF_files_replayed": len(replay.documents),
        "scope_fragments_replayed": scope_fragments, "evidence_fragments_replayed": evidence_fragments,
        "correction_blocks": correction_uses, "corrected_characters_in_one_block": len(differences),
        "model_input_payloads_checked": len(inputs), "unchanged_denominator": 20, "query_changed_points": 9,
        "all_ten_evidence_candidates_retained": True, "CPU_token_identity_receipt_current": True,
        "maximum_total_tokens": max(r["required_total"] for r in budgets), "no_truncation": True,
        "scope_holds": holds, "human_labels_written": 0, "joint_adjudications": 0,
        "formal_v3_input_release": False, "new_model_runs": 0, "GPU_used": False,
        "formal_location_rate": None, "engineering_accepted": 0, "local_links_checked": link_count,
        "files_sha256": {p.name: gate.sha(p) for p in sorted(prepared.iterdir()) if p.is_file() and p != args.output},
    }
    gate.write_json(args.output, report)
    print("FINAL_PREPARATION_AUDIT_PASS points=20 candidates=200 token_budget_pass=20 scope_holds=2; no model execution or human acceptance")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-root", "source-zip", "incoming-dir", "return-replay-summary", "prepared-dir", "pymupdf-dir", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    audit(parser.parse_args())


if __name__ == "__main__":
    main()
