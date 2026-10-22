"""CPU replay of the exact received BM25 functions; never run received main().

The received file creates a hard-coded output directory at module import time.
Load only inspected imports, retrieval constants and six pure/read-only function
definitions using AST; inject the local immutable PDF_TEXT_DIR. Preserve the
original file bytes and log this loading method instead of silently rewriting it.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys

import run_route1_pdf_v3 as gate

EXPECTED_SCRIPT_SHA256 = "e9e7b5c6cacb275f07e85dbdbd8acf15527c1b3e321f2bb886745abb69112521"
CONSTANTS = {"TOP_K", "BM25_K1", "BM25_B", "TOKEN_RE", "MIN_BLOCK_CHARS", "REF_PATTERN", "LOW_CONFIDENCE_SCORE"}
FUNCTIONS = {"tokenize", "file_sha256", "is_reference_block", "load_blocks", "build_bm25", "retrieve_case"}


def original_functions(script, source_root):
    gate.require(gate.sha(script) == EXPECTED_SCRIPT_SHA256, "Received script differs from the reviewed exact version")
    tree = ast.parse(script.read_text(encoding="utf-8-sig"), filename=str(script))
    kept = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            kept.append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in CONSTANTS:
                kept.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            kept.append(node)
    scope = {"__name__": "received_bm25_functions_only", "__file__": str(script),
             "PDF_TEXT_DIR": source_root / "pdf_text"}
    exec(compile(ast.Module(body=kept, type_ignores=[]), str(script), "exec"), scope)
    gate.require(FUNCTIONS.issubset(scope), "Expected retrieval definitions missing")
    return scope


def replay(source_root, incoming, prior_review, output, deps):
    source_root, incoming, prior_review, output = [Path(p).resolve() for p in (source_root, incoming, prior_review, output)]
    gate.require(not output.exists(), "Output exists; do not overwrite a replay")
    gate.require(not output.is_relative_to(source_root) and not source_root.is_relative_to(output), "Keep output outside original source package")
    sys.path.insert(0, str(Path(deps).resolve()))
    import numpy
    import rank_bm25
    version = importlib.metadata.version("rank-bm25")
    gate.require(version == "0.2.2", f"Wrong rank-bm25 version: {version}")
    lock = gate.read_json(source_root / "scope_lock.json")
    for name, expected in lock["files_sha256"].items():
        gate.require(gate.sha(source_root / name) == expected, f"Source scope changed: {name}")
    source_manifest = gate.read_json(source_root / "SHA256SUMS.json")["files"]
    requests = gate.load_jsonl(source_root / "cited_retrieval_requests.jsonl")
    prior = gate.read_json(prior_review / "retrieval_return_validation.json")
    received = gate.keyed(gate.load_jsonl(incoming / "cited_evidence_results.jsonl"), "case_id")
    gate.require(len(requests) == len(received) == 20 and {r["case_id"] for r in requests} == set(received), "Wrong fixed case set")
    incoming_hashes = {p.name: gate.sha(p) for p in incoming.iterdir() if p.is_file()}
    core = ("cited_evidence_results.jsonl", "cited_evidence_summary_top3.csv", "retrieval_manifest.json")
    gate.require(all(incoming_hashes[name] == prior["incoming_files_sha256"][name] for name in core), "Core results changed; repeat PDF locator audit before reuse")
    checked = set()
    for request in requests:
        cited = request["cited_pdf"]
        if cited["sha256"] in checked:
            continue
        block_relative = f"pdf_text/{cited['sha256']}/blocks.jsonl"
        gate.require(gate.sha(source_root / block_relative) == source_manifest[block_relative]["sha256"], "Cached PDF blocks changed")
        gate.require(gate.sha(source_root / cited["relative_path"]) == cited["sha256"], "Actual cited PDF changed")
        checked.add(cited["sha256"])
    script = incoming / "route1_pdf20_cited_retrieval_v1.py"
    scope = original_functions(script, source_root)
    output.mkdir(parents=True)
    (output / "supplement_files").mkdir()
    for name in ("route1_pdf20_cited_retrieval_v1.py", "复现材料补充说明_陈明进_20261020.md", "被引端检索结果说明_陈明进_20261020.md"):
        shutil.copyfile(incoming / name, output / "supplement_files" / name)
        gate.require(gate.sha(output / "supplement_files" / name) == incoming_hashes[name], "Archived supplement differs")
    started = datetime.now(timezone.utc).isoformat()
    recreated, comparisons = [], []
    with (output / "cpu_replay.log").open("w", encoding="utf-8") as log:
        def emit(message):
            print(message, flush=True)
            log.write(message + "\n")
            log.flush()
        emit(f"CPU_REPLAY_STARTED {started}; Python={platform.python_version()}; rank_bm25={version}; numpy={numpy.__version__}")
        emit("Original main(), hard-coded path assignments, and output-directory creation NOT executed.")
        for number, request in enumerate(requests, 1):
            result = scope["retrieve_case"](request)
            expected = received[request["case_id"]]
            recreated.append(result)
            differences = [key for key in set(result) | set(expected) if result.get(key) != expected.get(key)]
            comparison = {"case_id": request["case_id"], "all_record_fields_equal": not differences,
                          "different_fields": sorted(differences),
                          "candidate_order_and_six_decimal_scores_equal": result.get("candidates") == expected.get("candidates"),
                          "status": result["status"], "candidates": len(result["candidates"])}
            comparisons.append(comparison)
            emit(f"[{number:02d}/20] {request['case_id']} equal={not differences} candidates={comparison['candidates']} status={result['status']}")
    gate.write_jsonl(output / "cpu_recomputed_results.jsonl", recreated)
    candidate_matches = sum(len(r["candidates"]) for r, c in zip(recreated, comparisons)
                            if c["candidate_order_and_six_decimal_scores_equal"])
    passed = all(c["all_record_fields_equal"] for c in comparisons)
    for name, expected in incoming_hashes.items():
        gate.require(gate.sha(incoming / name) == expected, "Incoming file changed during replay")
    report = {
        "status": "passed_CPU_BM25_replay_only" if passed else "failed_CPU_BM25_replay",
        "replay_started_at_utc": started, "replay_finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "reported_original_execution": {"date": "2026-10-20", "time_precision": "date", "exact_time": None,
                                        "stdout_stderr_log": "not saved, explicitly disclosed by producer"},
        "replay_wrapper_sha256": gate.sha(Path(__file__)), "received_script_sha256": gate.sha(script),
        "declared_script_sha256_matches_actual": gate.sha(script) == EXPECTED_SCRIPT_SHA256,
        "execution_method": "AST: inspected imports + original retrieval constants/functions only; actual source file unmodified; injected local PDF_TEXT_DIR; did not execute original main or top-level mkdir",
        "reported_original_environment": "arm4r_py39 / Python 3.9", "replay_python": platform.python_version(),
        "rank_bm25_version": version, "rank_bm25_module_sha256": gate.sha(Path(rank_bm25.__file__)),
        "numpy_version": numpy.__version__, "source_scope_files_sha256": lock["files_sha256"],
        "incoming_files_sha256": incoming_hashes,
        "same_core_result_files_as_previous_audited_return": list(core),
        "previous_locator_audit_sha256": gate.sha(prior_review / "retrieval_return_validation.json"),
        "locator_proof_reuse": "200 candidates unchanged byte-for-byte; previous actual-PDF/offset/bbox replay remains applicable",
        "checked_cited_pdf_and_cache_versions": len(checked), "fixed_case_count": len(requests),
        "all_record_fields_equal_cases": sum(c["all_record_fields_equal"] for c in comparisons),
        "candidate_order_and_score_matches": candidate_matches, "comparisons": comparisons,
        "local_replay_log_sha256": gate.sha(output / "cpu_replay.log"),
        "recomputed_results_sha256": gate.sha(output / "cpu_recomputed_results.jsonl"),
        "source_script_not_general_entry": "Original paths are author-local and mkdir runs on import; this replay wrapper avoids those writes. Use a portable controlled entry for future runs.",
        "implementation_note": "Reference filtering is the actual regex/first-word heuristic, not a page-position filter; the function docstring mentions the latter but the code does not implement it.",
        "not_resolved_by_this_replay": ["Case 3 E02 text-layer prime/zero mismatch", "20 target-claim scopes including Case 15 resource/self-report boundary",
                                         "real tokenizer input budget", "classifier and independent explainer A100 runs", "both human reviews/adjudication"],
        "v3_input_configuration_frozen": False, "model_runs": 0, "engineering_accepted": 0,
        "formal_location_rate": None, "human_semantic_acceptance": None,
    }
    gate.write_json(output / "cpu_replay_summary.json", report)
    print(f"CPU_REPLAY_RESULT={'PASS' if passed else 'FAIL'} equal_cases={report['all_record_fields_equal_cases']}/20 matched_candidates={candidate_matches}/200")
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--incoming-dir", type=Path, required=True)
    parser.add_argument("--previous-review-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bm25-deps", type=Path, required=True)
    args = parser.parse_args()
    passed = replay(args.source_root, args.incoming_dir, args.previous_review_dir, args.output_dir, args.bm25_deps)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
