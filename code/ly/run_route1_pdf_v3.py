"""CPU preparation gate for the fixed Route 1 PDF batch; no model execution.

Read the immutable source package, replay PDF coordinates, accept cited-side
retrieval returns, and export per-point states and provisional model inputs.
Neither technical replay nor candidate retrieval is a semantic acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_sarol_inputs_v2 import SYSTEM_PROMPT, model_input_sha256, render_user_prompt

PDF_VERSION = "1.28.2"
OFFSET_BASIS = "PyMuPDF page.get_text(text, sort=False); Unicode code points; zero-based half-open"
BBOX_SCOPE = "whole intersecting text blocks, not exact sentence boxes"
RETURN_SCHEMA = "route1_cited_pdf_return_v2"
PREP_SCHEMA = "route1_pdf_preparation_v2_20261020"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def keyed(rows, key, known=None):
    result = {}
    for row in rows:
        value = row.get(key)
        require(isinstance(value, str) and value, f"Missing/non-string {key}")
        require(value not in result, f"Duplicate {key}: {value}")
        require(known is None or value in known, f"Unknown {key}: {value}")
        result[value] = row
    return result


def marker_inside(marker, fragments):
    return any(marker["pdf_page"] == fragment["pdf_page"]
               and fragment["char_start"] <= marker["char_start"]
               and marker["char_end_exclusive"] <= fragment["char_end_exclusive"]
               for fragment in fragments)


def relative_file(root, relative):
    require(isinstance(relative, str) and relative, "A portable relative path is required")
    target = (root / relative).resolve()
    require(target.is_relative_to(root.resolve()), f"Path outside source package: {relative}")
    require(target.is_file(), f"Source file missing: {relative}")
    return target


def import_pdf(extra_path=None):
    if extra_path:
        sys.path.insert(0, str(Path(extra_path).resolve()))
    import pymupdf
    require(pymupdf.VersionBind == PDF_VERSION,
            f"Offset replay requires PyMuPDF {PDF_VERSION}, got {pymupdf.VersionBind}; do not silently rebase offsets")
    return pymupdf


class PdfReplay:
    def __init__(self, pdf_module):
        self.module = pdf_module
        self.documents = {}

    def open(self, root, record):
        path = relative_file(root, record["relative_path"])
        expected = record["sha256"]
        cache_key = (str(path), expected)
        if cache_key not in self.documents:
            require(sha(path) == expected, f"PDF hash mismatch: {path.name}")
            require(path.read_bytes()[:5] == b"%PDF-", f"Not a PDF: {path.name}")
            document = self.module.open(path)
            require(not document.needs_pass and len(document) > 0, f"Unreadable PDF: {path.name}")
            self.documents[cache_key] = document
        return self.documents[cache_key]

    def close(self):
        for document in self.documents.values():
            document.close()

    def fragment(self, document, fragment):
        page_no = fragment.get("pdf_page")
        start, end = fragment.get("char_start"), fragment.get("char_end_exclusive")
        require(type(page_no) is int and 1 <= page_no <= len(document), "PDF page must be an in-range one-based integer")
        require(type(start) is int and type(end) is int and 0 <= start < end, "Invalid half-open character span")
        require(fragment.get("offset_basis") == OFFSET_BASIS, "Unknown/XML/normalized offset basis")
        require(fragment.get("bbox_scope") == BBOX_SCOPE, "Bounding box granularity must be explicitly block-level")
        page = document[page_no - 1]
        page_text = page.get_text("text", sort=False)
        require(end <= len(page_text), "Character span extends beyond page")
        raw = page_text[start:end]
        require(fragment.get("raw_text") == raw, "Raw quote does not match PDF character span")
        require(fragment.get("raw_text_sha256") == text_sha(raw), "Raw quote hash mismatch")
        expected_blocks, cursor = [], 0
        for number, block in enumerate(page.get_text("blocks", sort=False), 1):
            if len(block) > 6 and block[6] != 0:
                continue
            raw_block = str(block[4])
            block_start = page_text.find(raw_block, cursor)
            require(block_start >= 0, "PyMuPDF text/block extraction mismatch")
            cursor = block_start + len(raw_block)
            if block_start < end and start < cursor:
                expected_blocks.append({"block_number": number, "bbox": [round(float(x), 3) for x in block[:4]]})
        actual = fragment.get("source_blocks")
        require(isinstance(actual, list) and len(actual) == len(expected_blocks) and actual,
                "Incomplete/extra block bounding boxes")
        for given, expected in zip(actual, expected_blocks):
            require(given.get("block_number") == expected["block_number"], "Wrong PDF block number")
            box = given.get("bbox")
            require(isinstance(box, list) and len(box) == 4, "Invalid bounding box")
            require(all(type(x) in (int, float) and math.isfinite(x) and abs(x - y) <= 0.002
                        for x, y in zip(box, expected["bbox"])), "Bounding box does not reproduce PDF block")
        return raw


def validate_retrieval(case, pair, response, replay, cited_document):
    if response is None:
        return "awaiting_cited_retrieval", [], None
    require(response.get("schema_version") == RETURN_SCHEMA, "Unknown retrieval return schema")
    require(response.get("case_id") == case["case_id"], "Retrieval case mismatch")
    require(response.get("pair_id") == case["pair_id"], "Retrieval pair mismatch")
    require(response.get("cited_pdf_sha256") == pair["cited"]["sha256"], "Cross-PDF evidence is forbidden")
    status = response.get("retrieval_status")
    require(status in ("pending", "ok", "no_reliable_evidence"), "Unknown retrieval status")
    candidates = response.get("candidates")
    require(isinstance(candidates, list), "Retrieval candidates must be a list")
    if status != "ok":
        require(not candidates, "Pending/failed retrieval must not carry active evidence")
        require(status == "pending" or bool(str(response.get("note") or "").strip()),
                "No-evidence return requires a reason")
        return ("awaiting_cited_retrieval" if status == "pending" else "no_reliable_evidence"), [], response
    require(response.get("parser") == {"name": "PyMuPDF", "version": PDF_VERSION}, "PDF parser/version is not fixed")
    config = response.get("retrieval_config")
    require(isinstance(config, dict) and isinstance(config.get("method"), str)
            and config["method"].casefold() == "bm25"
            and isinstance(config.get("version"), str) and config["version"].strip(),
            "Retrieval method/version missing")
    parameters = config.get("parameters")
    require(isinstance(parameters, dict), "Actual BM25 parameters missing")
    k1, b = parameters.get("k1"), parameters.get("b")
    require(type(k1) in (int, float) and math.isfinite(k1) and k1 > 0
            and type(b) in (int, float) and math.isfinite(b) and 0 <= b <= 1, "Invalid BM25 k1/b parameters")
    require(config.get("corpus_pdf_sha256") == pair["cited"]["sha256"], "Retrieval corpus must be this cited PDF only")
    require(isinstance(config.get("query"), str) and config["query"].strip(), "Actual retrieval query missing")
    require(type(config.get("top_k")) is int and 1 <= len(candidates) <= config["top_k"],
            "Require nonempty candidates and an actual positive top_k covering all returned candidates")
    require(type(config.get("candidate_pool_size")) is int and config["candidate_pool_size"] >= len(candidates),
            "Actual candidate pool size missing or smaller than returned candidates")
    budget = config.get("input_budget")
    require(isinstance(budget, dict) and type(budget.get("max_length")) is int
            and type(budget.get("max_new_tokens")) is int
            and 0 < budget["max_new_tokens"] < budget["max_length"], "Declared input/generation budget missing or invalid")
    completed = response.get("retrieval_completed_at")
    require(isinstance(completed, str) and completed.strip(), "Actual retrieval completion time missing")
    try:
        timestamp = datetime.fromisoformat(completed.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Retrieval completion time must be ISO-8601") from error
    require(timestamp.tzinfo is not None, "Retrieval completion time needs a timezone")
    require(isinstance(response.get("producer"), str) and response["producer"].strip(), "Retrieval producer missing")
    keyed(candidates, "evidence_id")
    seen_spans, validated = set(), []
    for index, candidate in enumerate(candidates, 1):
        require(type(candidate.get("retrieval_rank")) is int and candidate["retrieval_rank"] == index,
                "Retrieval ranks must preserve the actual returned order, starting at one")
        score = candidate.get("retrieval_score")
        require(type(score) in (int, float) and math.isfinite(score), "Finite retrieval score missing")
        require(candidate.get("source_pdf_sha256") == pair["cited"]["sha256"], "Candidate belongs to another PDF")
        fragments = candidate.get("pdf_fragments")
        require(isinstance(fragments, list) and fragments, "Evidence requires actual PDF fragments, not XML locators")
        keys = [(f.get("pdf_page"), f.get("char_start"), f.get("char_end_exclusive")) for f in fragments]
        require(all(all(type(x) is int for x in key) for key in keys), "Evidence coordinates must be integers")
        require(keys == sorted(keys) and len(keys) == len(set(keys)), "Evidence fragments must be ordered and unique")
        require(all(left[0] != right[0] or left[2] <= right[1] for left, right in zip(keys, keys[1:])),
                "Evidence fragments must not overlap and duplicate original text")
        raw_parts = [replay.fragment(cited_document, f) for f in fragments]
        require(candidate.get("text") == "\n".join(raw_parts), "Evidence text must be joined unchanged PDF fragments")
        span_key = tuple(keys)
        require(span_key not in seen_spans, "Duplicate evidence span under another ID")
        seen_spans.add(span_key)
        validated.append({
            "evidence_id": f"D01:S{index:02d}", "source_evidence_id": candidate["evidence_id"],
            "retrieval_rank": candidate["retrieval_rank"], "retrieval_score": score,
            "text": candidate["text"], "source_pdf_sha256": candidate["source_pdf_sha256"],
            "pdf_fragments": fragments,
        })
    return "cited_locations_machine_replayed_pending_human_review", validated, response


def csv_safe(value):
    # Protect spreadsheet users without changing the authoritative JSONL text.
    value = "" if value is None else str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def code_provenance():
    repo = HERE.parents[1]
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--",
                             "code/ly/run_route1_pdf_v3.py", "code/ly/test_route1_pdf_v3.py",
                             "code/ly/README_route1_pdf_v3.md"], capture_output=True, text=True)
    return {"repository_head": head.stdout.strip() if head.returncode == 0 else None,
            "entry_files_status": status.stdout.splitlines() if status.returncode == 0 else None,
            "note": "Repository HEAD is the base commit, not proof these new local files are committed; file hashes identify the actual implementation."}


def prepare(source_root, output_dir, pdf_module, retrieval_return=None):
    root, out = Path(source_root).resolve(), Path(output_dir).resolve()
    require(not out.is_relative_to(root) and not root.is_relative_to(out), "Output and immutable source directories must be separate")
    require(not out.exists(), "Output already exists; choose a new directory, never overwrite a receipt")
    lock = read_json(root / "scope_lock.json")
    require(lock.get("case_count") == 20, "This gate is for the fixed 20-point batch")
    for name, expected in lock["files_sha256"].items():
        require(sha(relative_file(root, name)) == expected, f"Scope lock mismatch: {name}")
    cases = load_jsonl(root / "case_manifest.jsonl")
    case_map = keyed(cases, "case_id")
    require(len(cases) == 20, "Do not reduce the frozen 20-point denominator")
    pairs = keyed(load_jsonl(root / "pair_manifest.jsonl"), "pair_id")
    returns = keyed(load_jsonl(retrieval_return), "case_id", case_map) if retrieval_return else {}
    replay = PdfReplay(pdf_module)
    records, drafts, templates, point_keys = [], [], [], set()
    try:
        for case in cases:
            require(case.get("route") == "route1", "Not a Route 1 case")
            pair = pairs[case["pair_id"]]
            citing = replay.open(root, pair["citing"])
            cited = replay.open(root, pair["cited"])
            for field in ("citation_marker_locator", "citation_group_locator", "citing_context_raw_fragments",
                          "target_claim_scope_pdf_fragments", "reference_pdf_title_locator"):
                require(isinstance(case.get(field), list) and case[field], f"Missing citing PDF locator: {field}")
                for fragment in case[field]:
                    replay.fragment(citing, fragment)
            require(case["citation_marker_pdf_raw"] == [f["raw_text"] for f in case["citation_marker_locator"]],
                    "Displayed citation marker differs from raw PDF marker")
            for marker in case["citation_marker_locator"]:
                for field in ("citation_group_locator", "citing_context_raw_fragments", "target_claim_scope_pdf_fragments"):
                    require(marker_inside(marker, case[field]), f"Citation marker is outside its recorded {field}")
            marker_key = tuple((f["pdf_page"], f["char_start"], f["char_end_exclusive"])
                               for f in case["citation_marker_locator"])
            point_key = (pair["citing"]["sha256"], marker_key, pair["cited"]["sha256"])
            require(point_key not in point_keys, "Duplicate physical citation point")
            point_keys.add(point_key)
            payload = case["dedup_key_payload"]
            require(payload["citing_pdf_sha256"] == point_key[0] and payload["cited_pdf_sha256"] == point_key[2],
                    "Physical point PDF identity differs from frozen dedup key")
            require(payload["marker_locations"] == [{k: f[k] for k in ("pdf_page", "char_start", "char_end_exclusive")}
                                                     for f in case["citation_marker_locator"]], "Physical marker changed")
            selected = case["classifier_preselected"]
            require(case["domain"] == "biomedicine" and selected["name"] == "Mbio"
                    and selected["checkpoint"] == "checkpoint-100" and selected["reasoning"] is False,
                    "Unsupported/preselection-changed domain or adapter; do not guess from model predictions")
            status, evidence, response = validate_retrieval(case, pair, returns.get(case["case_id"]), replay, cited)
            record = {
                "schema_version": PREP_SCHEMA, "case_id": case["case_id"], "pair_id": case["pair_id"],
                "route": case["route"], "domain": case["domain"], "domain_basis": case["domain_basis"],
                "dedup_key": case["dedup_key"], "dedup_key_payload": case["dedup_key_payload"],
                "source_case_manifest_sha256": lock["files_sha256"]["case_manifest.jsonl"],
                "source_scope_locked_before_new_inference": case["source_scope_locked_before_new_inference"],
                "sample_set": case["sample_set"],
                "prior_annotation_exposure_note": case["prior_annotation_exposure_note"],
                "shared_route2_sample_overlap": case["shared_route2_sample_overlap"],
                "route2_overlap_audit_scope": case["route2_overlap_audit_scope"],
                "shared_citing_article_with_legacy_route2_points": case["shared_citing_article_with_legacy_route2_points"],
                "source_pool_candidate_id": case["source_pool_candidate_id"],
                "citing_pdf": pair["citing"], "cited_pdf": pair["cited"],
                "citing_context": case["citing_context"], "citing_context_marked": case["citing_context_marked"],
                "citation_marker_pdf_raw": case["citation_marker_pdf_raw"],
                "citation_group_pdf_raw": case["citation_group_pdf_raw"],
                "target_claim_scope_proposal": case["target_claim_scope_proposal"],
                "target_scope_review_status": case["target_scope_review_status"],
                "citation_marker_locator": case["citation_marker_locator"],
                "citing_context_raw_fragments": case["citing_context_raw_fragments"],
                "target_claim_scope_pdf_fragments": case["target_claim_scope_pdf_fragments"],
                "reference_pdf_title_locator": case["reference_pdf_title_locator"],
                "source_pdf_replay": "passed_technical_replay_only", "retrieval_status": status,
                "retrieval_return": response, "candidate_evidence": evidence,
                "returned_candidate_count": len(evidence),
                "classifier_preselected": selected, "model_prediction": None, "classifier_actual_run": None,
                "explanation_actual_run": None, "selected_evidence_ids": [], "reason": None,
                "confidence": None, "confidence_status": "uncalibrated",
                "score_support": None, "score_distort": None, "score_unrelated": None,
                "reviewers": case["reviewers"], "adjudicated_label": case["adjudicated_label"],
                "engineering_status": "not_run", "locator_review_status": "pending_human_review",
                "explanation_semantic_status": "not_run", "classification_status": "not_run",
                "end_to_end_accepted": False,
            }
            require(record["adjudicated_label"] is None and all(v.get("label") is None for v in record["reviewers"].values()),
                    "Unexpected labels in the immutable source batch")
            records.append(record)
            templates.append({
                "schema_version": RETURN_SCHEMA, "case_id": case["case_id"], "pair_id": case["pair_id"],
                "cited_pdf_sha256": pair["cited"]["sha256"], "retrieval_status": "pending",
                "parser": {"name": "PyMuPDF", "version": PDF_VERSION},
                "retrieval_config": {"method": "BM25", "version": None, "query": None, "top_k": None,
                                     "parameters": {"k1": None, "b": None}, "candidate_pool_size": None,
                                     "input_budget": {"max_length": None, "max_new_tokens": None},
                                     "corpus_pdf_sha256": pair["cited"]["sha256"]},
                "retrieval_completed_at": None, "producer": None, "candidates": [], "note": "",
            })
            if evidence:
                # Drafts are deliberately not an inference-ready acceptance: the
                # automatic target-sentence proposal still needs scope review.
                user = render_user_prompt(case["target_claim_scope_proposal"], evidence)
                drafts.append({"claim_id": case["case_id"], "system_prompt": SYSTEM_PROMPT,
                               "user_prompt": user, "input_sha256": model_input_sha256(SYSTEM_PROMPT, user),
                               "stage": "provisional_input_not_approved_for_model_execution",
                               "target_scope_review_status": case["target_scope_review_status"]})
        pdf_count = len({expected_hash for _, expected_hash in replay.documents})
    finally:
        replay.close()
    out.mkdir(parents=True)
    write_jsonl(out / "point_status.jsonl", records)
    write_jsonl(out / "cited_return_template.jsonl", templates)
    write_jsonl(out / "classification.provisional.inputs.jsonl", drafts)
    status_names = {
        "awaiting_cited_retrieval": "待陈明进回填被引 PDF 检索结果",
        "no_reliable_evidence": "未取得可靠被引证据，保留待核",
        "cited_locations_machine_replayed_pending_human_review": "被引位置机器回放通过，待人工核查证据语义",
    }
    view = ["路线一 PDF 20 点：本地接入检查（2026-10-20）", "",
            "本次仅检查文件与位置，未加载模型、未使用 GPU、未判定引用标签。",
            "20 个引用点、10 对 PDF、16 份不同 PDF；不是 20 条已经验收合格的样本。",
            "字符偏移为原始 PDF 提取文本的 Unicode 码点，零起始半开区间；bbox 为整块边界。", ""]
    for number, record in enumerate(records, 1):
        locations = "; ".join(f"PDF第{f['pdf_page']}页 [{f['char_start']},{f['char_end_exclusive']})"
                              for f in record["citation_marker_locator"])
        view.extend([f"{number:02d}. {record['case_id']} / {record['source_pool_candidate_id']}",
                     f"施引：{record['citing_pdf']['pmcid']} {record['citing_pdf']['title']}",
                     f"被引：{record['cited_pdf']['pmcid']} {record['cited_pdf']['title']}",
                     f"引用标记：{' | '.join(record['citation_marker_pdf_raw'])}；{locations}",
                     f"待核范围建议：{record['target_claim_scope_proposal']}",
                     f"状态：施引位置机器回放通过；{status_names[record['retrieval_status']]}",
                     "分类、解释、双方人工判断与裁决：尚未执行；不计入闭环验收。", ""])
    (out / "逐条状态.txt").write_text("\n".join(view), encoding="utf-8-sig")
    fields = ["case_id", "source_pool_candidate_id", "pair_id", "source_pdf_replay", "retrieval_status",
              "target_scope_review_status", "model_prediction", "engineering_status", "locator_review_status",
              "explanation_semantic_status", "classification_status", "end_to_end_accepted"]
    with (out / "point_status.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: csv_safe(r.get(k)) for k in fields} for r in records)
    receipt = {
        "schema_version": PREP_SCHEMA, "python": platform.python_version(), "pymupdf": pdf_module.VersionBind,
        "scope_lock_sha256": sha(root / "scope_lock.json"), "scope_files": lock["files_sha256"],
        "source_root": str(root), "script_sha256": sha(Path(__file__)),
        "code_provenance": code_provenance(),
        "frozen_prompt_source_sha256": sha(HERE / "build_sarol_inputs_v2.py"),
        "retrieval_return_sha256": sha(retrieval_return) if retrieval_return else None,
        "physical_citation_points": len(point_keys), "pdf_pairs": len({r["pair_id"] for r in records}),
        "unique_actual_pdfs_replayed": pdf_count, "citing_locator_replayed_points": len(records),
        "retrieval_status_counts": dict(Counter(r["retrieval_status"] for r in records)),
        "provisional_input_records": len(drafts), "inference_ready_records": 0,
        "classification_run": False, "explanation_run": False, "gpu_used": False,
        "engineering_accepted": 0, "location_validity_denominator": 20,
        "location_validity_numerator": None, "location_validity_rate": None,
        "explanation_semantic_passed": None, "classification_accuracy": None,
        "human_joint_signoff": lock["human_joint_signoff"],
        "note": "Technical PDF replay only. No semantic labels, model calls, formal validity rate or end-to-end acceptance.",
        "generated_files_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    write_json(out / "preparation_receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--retrieval-return", type=Path)
    parser.add_argument("--pymupdf-dir", type=Path, help="Optional directory containing pinned PyMuPDF 1.28.2")
    args = parser.parse_args()
    result = prepare(args.source_root, args.output_dir, import_pdf(args.pymupdf_dir), args.retrieval_return)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
