"""CPU offline quote-mapping trial with fresh replay of frozen PDF offsets."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from pdf_quote_mapping_trial_v1 import VERSION, match_quote, unwrap_outer_json_fence


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def txtsha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def save_rows(path, values):
    Path(path).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in values), encoding="utf-8", newline="\n")


def inventory(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob("*") if p.is_file()}


def validate_body(obj, available):
    require(set(obj) == {"evidence_ids", "quotes", "reason"}, "Wrong explanation fields")
    ids = obj["evidence_ids"]
    require(isinstance(ids, list) and ids and all(isinstance(i, str) for i in ids), "Invalid IDs")
    require(len(ids) == len(set(ids)) and set(ids) <= set(available), "Duplicate/out-of-range IDs")
    require(isinstance(obj["reason"], str) and obj["reason"].strip(), "Missing reason")
    require(isinstance(obj["quotes"], list) and obj["quotes"], "Missing quotes")
    covered = set()
    for q in obj["quotes"]:
        require(isinstance(q, dict) and set(q) == {"evidence_id", "quote"}, "Wrong quote fields")
        require(q["evidence_id"] in ids and isinstance(q["quote"], str) and q["quote"].strip(), "Bad quote")
        covered.add(q["evidence_id"])
    require(covered == set(ids), "Selected evidence lacks quote")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("run-root", "snapshot", "policy", "repo-root", "pymupdf-dir", "output-dir"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    run, out = args.run_root.resolve(), args.output_dir.resolve()
    require(not out.exists() and not out.is_relative_to(run), "New output outside original run required")
    before = inventory(run)
    policy = read(args.policy)
    require(policy["version"] == VERSION and policy["accepted_production_parser"] is False, "Wrong trial policy")
    require(sha(args.snapshot) == policy["snapshot_sha256"], "Snapshot changed")
    request = read(run / "execution_request.json")
    code = args.repo_root.resolve() / "code/ly"
    for name, digest in request["original_contract_code_sha256"].items():
        require(sha(code / name) == digest, "Original frozen code changed: " + name)
    sys.path.insert(0, str(code))
    import route1_pdf_pipeline_v3 as contract
    import run_route1_pdf_v3 as source_gate
    pdf_module = source_gate.import_pdf(args.pymupdf_dir)
    replay = source_gate.PdfReplay(pdf_module)
    snapshots = jsonl(args.snapshot)
    all_records = jsonl(run / "assembled/records.jsonl")
    byid = {r["case_id"]: r for r in all_records}
    require(len(all_records) == 20 and request["fixed_denominator"] == 20, "Keep fixed 20 points")
    require([r["case_id"] for r in snapshots] == request["selected_case_ids"] and len(snapshots) == 5, "Wrong first5")
    documents, pdf_files, points, quotes = {}, {}, [], []
    fragment_count = 0
    try:
        for row in snapshots:
            original = byid[row["case_id"]]
            require(row["frozen_candidates_unchanged"] == original["retrieval"]["candidates"], "Candidates differ")
            require(row["raw_explanation_unchanged"] == original["explanation_response"]["raw_output"], "Response differs")
            require(txtsha(row["raw_explanation_unchanged"]) == row["raw_explanation_sha256"], "Response hash differs")
            for role in ("citing_pdf", "cited_pdf"):
                record = row[role]
                path = Path(record["path"])
                require(sha(path) == record["sha256"], "PDF hash differs: " + str(path))
                pdf_files[str(path)] = record["sha256"]
                if role == "cited_pdf" and str(path) not in documents:
                    documents[str(path)] = pdf_module.open(path)
            document = documents[str(Path(row["cited_pdf"]["path"]))]
            available = {c["evidence_id"]: c for c in row["frozen_candidates_unchanged"]}
            require(len(available) == 10, "Wrong evidence count")
            for c in available.values():
                require(len(c["pdf_fragments"]) == 1, "Trial rejects multi-fragment candidate")
                fragment = c["pdf_fragments"][0]
                require(c["raw_text"] == fragment["raw_text"], "Fragment/raw text mismatch")
                require(txtsha(c["raw_text"]) == c["raw_text_sha256"], "Raw hash mismatch")
                require(txtsha(c["model_text"]) == c["model_text_sha256"], "Model text hash mismatch")
                require(c["source_pdf_sha256"] == row["cited_pdf"]["sha256"], "Cross-PDF evidence")
                replay.fragment(document, fragment)
                fragment_count += 1
                require(len(c["raw_text"]) == len(c["model_text"]), "Length-changing patch needs explicit map")
                if c["raw_text"] != c["model_text"]:
                    require(c["correction_patch_ids"] == ["trimmomatic_p03_prime_glyphs_v1"], "Unknown patch")
                    require([(a, b) for a, b in zip(c["raw_text"], c["model_text"]) if a != b]
                            == [("0", "′"), ("0", "′")], "Known patch changed")
                else:
                    require(not c["correction_patch_ids"], "Unexpected patch marker")
            raw = row["raw_explanation_unchanged"]
            body, unfenced = unwrap_outer_json_fence(raw)
            obj = contract.strict_json(body)
            require(obj == row["body_for_reading_only"], "Body differs from snapshot")
            validate_body(obj, available)
            strict = contract.parse_explanation(raw, list(available.values()))
            fence = contract.parse_explanation(body, list(available.values()))
            require(strict == original["explanation_response"]["parsed"], "Original strict parse differs")
            local_quotes = []
            for qi, q in enumerate(obj["quotes"], 1):
                candidate = available[q["evidence_id"]]
                fragment = candidate["pdf_fragments"][0]
                result = match_quote(candidate["model_text"], q["quote"])
                for match in result["matches"]:
                    a, b = match["source_start"], match["source_end"]
                    require(match["raw_source_excerpt"] == candidate["model_text"][a:b], "Bad interval")
                    raw_quote = candidate["raw_text"][a:b]
                    pdf_a, pdf_b = fragment["char_start"] + a, fragment["char_start"] + b
                    page = document[fragment["pdf_page"] - 1]
                    require(page.get_text("text", sort=False)[pdf_a:pdf_b] == raw_quote, "Quote/PDF replay differs")
                    patches = [{"candidate_offset": i, "raw": candidate["raw_text"][i], "model": candidate["model_text"][i]}
                               for i in range(a, b) if candidate["raw_text"][i] != candidate["model_text"][i]]
                    match["PDF_mapping"] = {
                        "source_pdf_sha256": candidate["source_pdf_sha256"], "pdf_page": fragment["pdf_page"],
                        "printed_page": fragment["printed_page"], "char_start": pdf_a, "char_end_exclusive": pdf_b,
                        "raw_PDF_quote": raw_quote, "raw_PDF_quote_sha256": txtsha(raw_quote),
                        "source_blocks": fragment["source_blocks"], "bbox_scope": fragment["bbox_scope"],
                        "offset_basis": fragment["offset_basis"], "preexisting_patch_ids": candidate["correction_patch_ids"],
                        "preexisting_patch_differences": patches,
                        "fresh_PDF_character_replay_verified": True, "human_locator_signoff": False,
                    }
                    for m in match["character_map"]:
                        m["PDF_char_start"] = fragment["char_start"] + m["source_start"]
                        m["PDF_char_end_exclusive"] = fragment["char_start"] + m["source_end"]
                result.update({"case_id": row["case_id"], "quote_index": qi, "evidence_id": q["evidence_id"],
                               "original_model_quote": q["quote"], "original_model_quote_sha256": txtsha(q["quote"]),
                               "candidate_model_text_sha256": candidate["model_text_sha256"],
                               "formal_acceptance": False, "semantic_verified": False})
                quotes.append(result)
                local_quotes.append(result)
            points.append({
                "case_id": row["case_id"], "model_label_unchanged": row["model_label_unchanged"],
                "raw_response_sha256": row["raw_explanation_sha256"], "outer_fence_removed_for_diagnosis": unfenced,
                "original_strict_status": strict["status"], "fence_only_status": fence["status"],
                "quotes_total": len(local_quotes), "unique_mapped_quotes": sum(q["unique_mapping"] for q in local_quotes),
                "all_quotes_uniquely_mapped": all(q["unique_mapping"] for q in local_quotes),
                "line_join_review_required": any(q["line_join_review_required"] for q in local_quotes),
                "formal_end_to_end_accepted": False, "semantic_status": "pending_human_review",
            })
    finally:
        for document in documents.values():
            document.close()
        replay.close()
    require(inventory(run) == before and sha(args.snapshot) == policy["snapshot_sha256"], "Original files changed")
    require("torch" not in sys.modules, "Unexpected torch import")
    summary = {
        "version": VERSION, "status": "CPU_OFFLINE_MAPPING_TRIAL_NOT_FORMAL_ACCEPTANCE",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "recorded_client_date": "2026-10-23",
        "policy_sha256": sha(args.policy), "runner_sha256": sha(__file__),
        "mapper_sha256": sha(Path(__file__).with_name("pdf_quote_mapping_trial_v1.py")),
        "snapshot_sha256": sha(args.snapshot), "PyMuPDF": pdf_module.VersionBind,
        "first_batch_points": 5, "fixed_denominator": 20, "source_PDF_files_verified": len(pdf_files),
        "frozen_candidate_PDF_fragments_replayed": fragment_count,
        "quotes_total": len(quotes), "quotes_uniquely_mapped": sum(q["unique_mapping"] for q in quotes),
        "points_all_quotes_uniquely_mapped": sum(r["all_quotes_uniquely_mapped"] for r in points),
        "points_with_line_join_review_required": sum(r["line_join_review_required"] for r in points),
        "original_strict_points": sum(r["original_strict_status"] == "structure_and_quotes_valid_pending_human_semantics" for r in points),
        "fence_only_supplemental_points": sum(r["fence_only_status"] == "structure_and_quotes_valid_pending_human_semantics" for r in points),
        "formal_end_to_end_accepted": 0, "formal_location_rate": None, "semantic_verified": 0,
        "new_model_inference": False, "torch_imported": False, "GPU_used": False,
        "accepted_production_parser_changed": False, "original_artifacts_unchanged": True,
        "scope_limit": "Unique character mappings and layout hypotheses; not classification, semantics, human acceptance, or new formal engineering results.",
    }
    require(summary["original_strict_points"] == 1 and summary["fence_only_supplemental_points"] == 3, "Historical results differ")
    out.mkdir(parents=True)
    save_rows(out / "逐条摘录映射_非验收.jsonl", quotes)
    save_rows(out / "逐点诊断_非验收.jsonl", points)
    save(out / "诊断摘要.json", summary)
    save(out / "原始运行文件_SHA256.json", before)
    save(out / "来源PDF_SHA256.json", pdf_files)
    (out / args.policy.name).write_bytes(args.policy.read_bytes())
    lines = ["# PDF首批5点CPU离线摘录映射诊断", "",
             "单独版本的只读诊断，未采用为正式解析器，没有重新调用模型。", "",
             f"- 原严格结果：{summary['original_strict_points']}/5；仅去围栏补充结果：{summary['fence_only_supplemental_points']}/5。",
             f"- 当前试验：{summary['quotes_uniquely_mapped']}/{summary['quotes_total']}条摘录唯一映射；"
             f"{summary['points_all_quotes_uniquely_mapped']}/5点全部摘录可回指原候选及原PDF字符位置。",
             f"- {summary['points_with_line_join_review_required']}点包含删除行末连字符的断词假设，仍需复核。",
             f"- 验证{len(pdf_files)}份PDF哈希，PyMuPDF {pdf_module.VersionBind}重新回放{fragment_count}个候选片段。",
             "- 数值是摘录映射诊断，不是语义正确率、正式定位率或新的正式工程通过率。正式端到端验收仍为0，固定分母20。",
             "", "| 点 | 全部摘录唯一映射 | 断词假设需复核 |", "|---|---|---|"]
    for r in points:
        lines.append(f"| {r['case_id']} | {r['unique_mapped_quotes']}/{r['quotes_total']} | {'是' if r['line_join_review_required'] else '否'} |")
    lines.extend(["", "每条记录保留原quote、原文片段、字符映射、变换日志、PDF页与区块框。区块框不是精确句子框，机器回放不是人工签核。",
                  "已冻结5′/3′修订保留原始字形和补丁映射；未改变原文。普通词内连字符、数字、负号、否定词及上标不全局删除。",
                  "PDB数量、Trimmomatic修饰语、武汉识别日期及enveloped材料边界等语义待决保持。"])
    (out / "先看这里_离线诊断结论.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    save(out / "本目录_SHA256.json", inventory(out))
    require(inventory(run) == before, "Original run changed")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

