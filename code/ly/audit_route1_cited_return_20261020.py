"""Receive Chen's 20-point cited retrieval return without inventing annotations.

Replay all supplied PDF blocks and check identities, scores/ranks, cached source
blocks, CSV view, and manifest. Preserve source statuses as retrieval heuristics.
Missing execution provenance is reported, never fabricated for interface v2.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_route1_pdf_v3 as gate

RETURN_FILES = ("cited_evidence_results.jsonl", "cited_evidence_summary_top3.csv", "retrieval_manifest.json",
                "被引端检索结果说明_陈明进_20261020.md")


def read_rows(path):
    return gate.load_jsonl(path)


def audit(source, incoming, output, pdf_module):
    source, incoming, output = Path(source).resolve(), Path(incoming).resolve(), Path(output).resolve()
    gate.require(not output.exists(), "Output already exists; choose a new output directory")
    gate.require(not output.is_relative_to(source) and not source.is_relative_to(output),
                 "Output must be separate from the immutable source package")
    input_hashes = {name: gate.sha(incoming / name) for name in RETURN_FILES}
    lock = gate.read_json(source / "scope_lock.json")
    for name, expected in lock["files_sha256"].items():
        gate.require(gate.sha(source / name) == expected, f"Source scope hash mismatch: {name}")
    cases = gate.keyed(read_rows(source / "case_manifest.jsonl"), "case_id")
    pairs = gate.keyed(read_rows(source / "pair_manifest.jsonl"), "pair_id")
    rows = read_rows(incoming / "cited_evidence_results.jsonl")
    returned = gate.keyed(rows, "case_id", cases)
    gate.require(len(rows) == 20 and set(returned) == set(cases), "Return must cover all fixed 20 points exactly once")
    manifest = gate.read_json(incoming / "retrieval_manifest.json")
    summaries = gate.keyed(manifest["case_summary"], "case_id", cases)
    gate.require(set(summaries) == set(cases), "Manifest summary cases differ from source cases")
    declared = manifest["retrieval_config"]
    gate.require(declared["engine"] == "rank_bm25.BM25Okapi" and declared["k1"] == 1.2
                 and declared["b"] == 0.75 and declared["top_k"] == 10
                 and declared["min_block_chars"] == 50, "Unexpected declared retrieval configuration")
    source_hash_manifest = gate.read_json(source / "SHA256SUMS.json")["files"]
    replay = gate.PdfReplay(pdf_module)
    caches, records, actual_count = {}, [], 0
    failures = []
    try:
        for case_id, case in cases.items():
            raw = returned[case_id]
            pair = pairs[case["pair_id"]]
            for given, expected in (
                (raw["pair_id"], pair["pair_id"]), (raw["target_reference_id"], case["reference_id"]),
                (raw["cited_pmcid"], pair["cited"]["pmcid"]), (raw["cited_title"], pair["cited"]["title"]),
                (raw["cited_pdf_sha256"], pair["cited"]["sha256"]),
                (raw["cited_pdf_relative_path"], pair["cited"]["relative_path"]),
                (raw["query"], case["target_claim_scope_proposal"]),
                (raw["query_source"], "target_claim_scope_proposal"),
                (raw["retrieval_scope"], "this cited PDF only"),
                (raw["bm25_k1"], declared["k1"]), (raw["bm25_b"], declared["b"]), (raw["top_k"], declared["top_k"]),
            ):
                gate.require(given == expected, f"Identity/query/config mismatch in {case_id}")
            document = replay.open(source, pair["cited"])
            pdf_hash = raw["cited_pdf_sha256"]
            if pdf_hash not in caches:
                relative = f"pdf_text/{pdf_hash}/blocks.jsonl"
                gate.require(gate.sha(source / relative) == source_hash_manifest[relative]["sha256"], "Cached block file changed")
                blocks = read_rows(source / relative)
                caches[pdf_hash] = {(b["pdf_page"], b["block_number"]): b for b in blocks}
            cached = caches[pdf_hash]
            counts = [raw[k] for k in ("total_blocks", "blocks_filtered_short", "blocks_filtered_reference")]
            gate.require(all(type(x) is int and x >= 0 for x in counts), "Invalid block count")
            gate.require(len(cached) == sum(counts), "Filtered/retained block counts do not reconcile")
            candidates = raw["candidates"]
            gate.keyed(candidates, "evidence_id")
            gate.require(len(candidates) == raw["num_candidates_returned"] == 10, "Expected ten candidates per case")
            seen, normalized, last_score = set(), [], float("inf")
            case_errors = []
            for rank, candidate in enumerate(candidates, 1):
                gate.require(candidate["rank"] == rank and candidate["evidence_id"] == f"E{rank:02d}", "Candidate rank/ID changed")
                score = candidate["bm25_score"]
                gate.require(type(score) in (int, float) and math.isfinite(score) and score <= last_score,
                             "Nonfinite or unordered BM25 score")
                last_score = score
                key = (candidate["pdf_page"], candidate["block_number"])
                gate.require(key not in seen, "Duplicate candidate PDF block")
                seen.add(key)
                fragment = {k: candidate[k] for k in ("pdf_page", "char_start", "char_end_exclusive", "raw_text", "raw_text_sha256")}
                fragment.update(printed_page=None,
                                source_blocks=[{"block_number": candidate["block_number"], "bbox": candidate["bbox"]}],
                                offset_basis=gate.OFFSET_BASIS, bbox_scope=gate.BBOX_SCOPE)
                locator_status, problem = "passed_technical_replay_only", None
                try:
                    gate.PdfReplay.fragment(replay, document, fragment)
                    original = cached[key]
                    gate.require(all(candidate[k] == original[k] for k in
                                     ("char_start", "char_end_exclusive", "raw_text", "raw_text_sha256", "bbox")),
                                 "Returned candidate differs from immutable source block")
                    actual_count += 1
                except (ValueError, KeyError, TypeError) as error:
                    locator_status, problem = "failed_technical_replay", str(error)
                    issue = {"case_id": case_id, "evidence_id": candidate["evidence_id"], "reason": problem}
                    failures.append(issue)
                    case_errors.append(issue)
                normalized.append({"source_evidence_id": candidate["evidence_id"],
                                   "evidence_id": f"D01:S{rank:02d}", "retrieval_rank": rank, "retrieval_score": score,
                                   "source_pdf_sha256": pdf_hash, "text": candidate["raw_text"],
                                   "pdf_fragments": [fragment], "locator_replay": locator_status, "failure_reason": problem})
            expected_heuristic = "ok" if candidates[0]["bm25_score"] >= 15 else "low_confidence"
            gate.require(raw["status"] == expected_heuristic, "Reported raw score-threshold status differs from result")
            summary = summaries[case_id]
            gate.require(summary["cited_pmcid"] == raw["cited_pmcid"] and summary["status"] == raw["status"]
                         and summary["num_candidates"] == len(candidates)
                         and abs(summary["top1_score"] - candidates[0]["bm25_score"]) <= 1e-6
                         and summary["top1_page"] == candidates[0]["pdf_page"], "Manifest summary mismatch")
            records.append({
                "schema_version": "route1_cited_reception_review_v1", "case_id": case_id, "pair_id": case["pair_id"],
                "route": case["route"], "domain": case["domain"], "dedup_key": case["dedup_key"],
                "source_pool_candidate_id": case["source_pool_candidate_id"],
                "cited_pmcid": raw["cited_pmcid"], "cited_pdf_sha256": pdf_hash,
                "target_reference_id": case["reference_id"], "query_as_received": raw["query"],
                "target_scope_review_status": case["target_scope_review_status"],
                "citing_context_marked": case["citing_context_marked"],
                "original_retrieval_status": raw["status"], "original_note": raw["note"],
                "raw_status_meaning": "BM25 top1 score threshold 15; not label, probability, or semantic acceptance",
                "retrieval_config_as_received": declared,
                "candidate_pool_size": raw["total_blocks"], "original_source_block_count": len(cached),
                "returned_candidate_count": len(candidates), "candidate_evidence": normalized,
                "reception_status": "received_positions_replayed_scope_and_provenance_pending" if not case_errors else "received_with_locator_failures",
                "actual_retrieval_completed_at": None, "reported_retrieval_date": manifest["date"],
                "input_budget": None, "retrieval_script_sha256": None, "rank_bm25_version": None,
                "coordinate_provenance": "Source package cached PyMuPDF 1.28.2 blocks; all returned positions independently replayed against actual PDF here. Not a claim that Chen loaded PDF parser independently.",
                "prior_annotation_exposure_note": case["prior_annotation_exposure_note"],
                "model_prediction": None, "classifier_actual_run": None, "explanation_actual_run": None,
                "adjudicated_label": None, "confidence": None, "confidence_status": "uncalibrated",
                "score_support": None, "score_distort": None, "score_unrelated": None,
                "engineering_status": "not_run", "semantic_review_status": "pending", "end_to_end_accepted": False,
            })
    finally:
        replay.close()
    by_case = {r["case_id"]: r for r in rows}
    with (incoming / "cited_evidence_summary_top3.csv").open(encoding="utf-8-sig", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    gate.require(len(csv_rows) == 60, "CSV should contain the top three candidates for each of 20 cases")
    csv_keys, csv_query_preview_cases, csv_query_preview_rows = set(), set(), 0
    for row in csv_rows:
        key = row["case_id"], int(row["rank"])
        gate.require(key not in csv_keys and key[1] in (1, 2, 3), "Duplicate/out-of-range CSV rank")
        csv_keys.add(key)
        original_case = by_case[key[0]]
        candidate = original_case["candidates"][key[1] - 1]
        for csv_name, original in (("pair_id", original_case["pair_id"]), ("target_ref", original_case["target_reference_id"]),
                                   ("cited_pmcid", original_case["cited_pmcid"]),
                                   ("status", original_case["status"]), ("eid", candidate["evidence_id"])):
            gate.require(row[csv_name] == original, f"CSV/JSONL mismatch: {key} {csv_name}")
        if row["query"] != original_case["query"]:
            gate.require(len(row["query"]) == 200 and row["query"] == original_case["query"][:200],
                         f"Unexpected CSV query difference: {key}")
            csv_query_preview_cases.add(row["case_id"])
            csv_query_preview_rows += 1
        for field in ("pdf_page", "block_number", "char_start", "char_end_exclusive"):
            gate.require(int(row[field]) == candidate[field], f"CSV coordinate mismatch: {key} {field}")
        gate.require(abs(float(row["bm25_score"]) - candidate["bm25_score"]) <= 1e-6, "CSV score mismatch")
        gate.require(all(abs(float(row[f"bbox_{name}"]) - candidate["bbox"][i]) <= .002
                         for i, name in enumerate(("x0", "y0", "x1", "y1"))), "CSV bbox mismatch")
    gate.require(csv_keys == {(r["case_id"], rank) for r in rows for rank in (1, 2, 3)}, "CSV case coverage mismatch")
    statuses = Counter(r["status"] for r in rows)
    gate.require(manifest["stats"]["total"] == 20 and manifest["stats"]["ok"] == statuses["ok"]
                 and manifest["stats"]["low_confidence"] == statuses["low_confidence"], "Aggregate statistics mismatch")
    gate.require(input_hashes == {name: gate.sha(incoming / name) for name in RETURN_FILES}, "Incoming files changed during audit")
    output.mkdir(parents=True)
    (output / "original_return").mkdir()
    for name in RETURN_FILES:
        shutil.copyfile(incoming / name, output / "original_return" / name)
        gate.require(gate.sha(output / "original_return" / name) == input_hashes[name], "Archived original changed")
    gate.write_jsonl(output / "received_cited_evidence.jsonl", records)
    report = {
        "audited_at_utc": datetime.now(timezone.utc).isoformat(), "audit_script_sha256": gate.sha(Path(__file__)),
        "pdf_gate_script_sha256": gate.sha(Path(gate.__file__)), "pymupdf_for_local_replay": pdf_module.VersionBind,
        "source_scope_lock_sha256": gate.sha(source / "scope_lock.json"), "source_scope_files": lock["files_sha256"],
        "incoming_files_sha256": input_hashes, "fixed_points_received": 20, "fixed_points_missing": 0,
        "pdf_pairs": len({r["pair_id"] for r in rows}), "distinct_cited_pdfs": len(caches),
        "candidates_received": sum(len(r["candidates"]) for r in rows), "candidates_pdf_replay_passed": actual_count,
        "candidate_locator_failures": failures, "csv_top3_rows_checked": len(csv_rows),
        "csv_query_is_truncated_preview_in_cases": sorted(csv_query_preview_cases),
        "csv_query_truncated_case_count": len(csv_query_preview_cases),
        "csv_query_truncated_rows": csv_query_preview_rows,
        "csv_query_warning": "The query column is truncated to 200 characters for eight cases. Preserve original CSV as received, use full JSONL query for any computation, never use this CSV as model input.",
        "original_score_threshold_statuses": dict(statuses), "actual_cited_paper_point_counts": dict(Counter(r["cited_pmcid"] for r in rows)),
        "report_issue": "Explanation markdown lists PMC7159299 as six points; actual result JSONL and original fixed case set both contain five. Do not add or replace points.",
        "block_count_meaning": "total_blocks is the retained post-filter BM25 pool; retained + filtered_short + filtered_reference equals original cached block count in all 20 cases.",
        "producer_provenance_missing": ["Actual retrieval script and SHA-256", "rank_bm25 package version and exact reference-filter code", "Execution time has date only; no exact time/timezone supplied"],
        "local_work_pending": ["Review target citation/claim coverage before query freeze", "Compute real tokenizer input lengths and freeze input/generation budget", "Prepare classifier and independent explainer A100 runs", "Both human reviews and adjudication"],
        "no_retrieval_algorithm_or_score_recomputation_claimed": True,
        "no_threshold_15_semantic_acceptance_claimed": True, "classification_or_explanation_runs": 0,
        "inference_ready_points": 0, "engineering_accepted": 0, "formal_location_denominator": 20,
        "formal_location_numerator": None, "formal_location_rate": None, "human_semantic_acceptance": None,
        "generated_join_file_sha256": gate.sha(output / "received_cited_evidence.jsonl"),
    }
    gate.write_json(output / "retrieval_return_validation.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--incoming-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pymupdf-dir", type=Path)
    args = parser.parse_args()
    report = audit(args.source_root, args.incoming_dir, args.output_dir, gate.import_pdf(args.pymupdf_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
