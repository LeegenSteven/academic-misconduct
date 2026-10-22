"""Controlled PDF20 runtime: CPU preparation, release gate, separate model stages.

No GPU library is imported until an explicit run-* command passes release gates.
Frozen v2 experiments and original source/return files are never modified.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback

import run_route1_pdf_v3 as source_gate
import prepare_pdf20_scope_inputs_20261020 as preparation

VERSION = "route1_pdf_pipeline_v3_20261021"
LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")
ADAPTER_SHA = "0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09"
MAX_LENGTH, MAX_NEW = 5120, 512
EXPLANATION_SYSTEM = (
    "你是独立的学术引用证据解释模块，不是分类器。只依据当前被引文献的候选原文，核查目标引用覆盖的主张。"
    "必要上下文只用于解消指代。同句其他引用的主张不能归给当前文献。保留对象、数量、方向和条件；部分支持不能写成全部支持。"
    "不要使用外部知识，不推测缺失证据，不输出分类标签或置信度。"
    "仅输出JSON：{\"evidence_ids\":[\"D01:S01\"],\"quotes\":[{\"evidence_id\":\"D01:S01\",\"quote\":\"候选原文中连续、逐字一致的简短摘录\"}],\"reason\":\"说明证据支持、反驳或不能解决哪些具体主张，并明确限制\"}。"
    "编号只能来自所给候选；每个选中编号至少一处摘录，换行及符号也须原样保留。理由必须有证据，不得过度概括。"
    "若无法取得足够证据，只输出{\"failure_status\":\"insufficient_evidence\"}。"
)

require, sha = source_gate.require, source_gate.sha
read_json, read_jsonl = source_gate.read_json, source_gate.load_jsonl
def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8", newline="\n")


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def code_hashes():
    files = [Path(__file__), Path(__file__).with_name("route1_pdf_hf_backend_v3.py"),
             Path(source_gate.__file__), Path(preparation.__file__),
             Path(__file__).with_name("build_sarol_inputs_v2.py")]
    return {p.name: sha(p) for p in files}


def new_directory(path, source, prepared):
    path = Path(path).resolve()
    require(not path.exists(), "Output already exists; preserve earlier runs")
    require(not path.is_relative_to(Path(source).resolve()) and not path.is_relative_to(Path(prepared).resolve()),
            "Output cannot modify the immutable source or preparation directories")
    path.mkdir(parents=True)
    return path


def load_prepared(source, prepared, pdf_module):
    source, prepared = Path(source).resolve(), Path(prepared).resolve()
    summary = read_json(prepared / "preparation_summary.json")
    for filename, expected in summary["generated_files_sha256"].items():
        require(sha(source_gate.relative_file(prepared, filename)) == expected, f"Preparation changed: {filename}")
    policy = read_json(prepared / "preparation_policy_before_cpu_retrieval.json")
    for filename, expected in policy["source_scope_files_sha256"].items():
        require(sha(source_gate.relative_file(source, filename)) == expected, f"Source scope changed: {filename}")
    cases = read_jsonl(source / "case_manifest.jsonl")
    pairs = source_gate.keyed(read_jsonl(source / "pair_manifest.jsonl"), "pair_id")
    scopes = read_jsonl(prepared / "scope_review.jsonl")
    retrieval = read_jsonl(prepared / "retrieval_v2_preparation.jsonl")
    classification = read_jsonl(prepared / "classification.draft.inputs.jsonl")
    require(len(cases) == len(scopes) == len(retrieval) == len(classification) == 20, "Fixed denominator must remain 20")
    require(len({c["case_id"] for c in cases}) == len({c["dedup_key"] for c in cases}) == 20, "Duplicate physical point")
    correction = read_json(prepared / "text_layer_corrections.json")
    raw, model = correction["raw_text"], correction["model_text"]
    differences = [i for i, (a, b) in enumerate(zip(raw, model)) if a != b]
    require(len(raw) == len(model) and len(differences) == 2
            and differences == [p["within_block_index"] for p in correction["patches"]], "Unlogged transcription change")
    require(all(raw[i] == "0" and model[i] == "′" for i in differences), "Wrong transcription patch")
    replay, items = source_gate.PdfReplay(pdf_module), []
    try:
        for case, scope, retrieved, classifier in zip(cases, scopes, retrieval, classification):
            cid = case["case_id"]
            require(cid == scope["case_id"] == retrieved["case_id"] == classifier["claim_id"], "Unknown/reordered/missing point")
            require(case["pair_id"] == scope["pair_id"] == retrieved["pair_id"] and case["dedup_key"] == scope["dedup_key"], "Pair/point mismatch")
            pair = pairs[case["pair_id"]]
            require(case["domain"] == "biomedicine" and case["classifier_preselected"]["name"] == "Mbio"
                    and case["classifier_preselected"]["checkpoint"] == "checkpoint-100"
                    and case["classifier_preselected"]["adapter_sha256_expected"] == ADAPTER_SHA, "Domain/model preselection changed")
            citing, cited = replay.open(source, pair["citing"]), replay.open(source, pair["cited"])
            for f in case["reference_pdf_title_locator"] + case["citation_marker_locator"]:
                replay.fragment(citing, f)
            require(scope["original_full_context_marked"] == case["citing_context_marked"], "Original context changed")
            primary_fragments = []
            for key in ("primary_scope_pieces", "context_only_pieces"):
                for part in scope[key]:
                    require(case["citing_context"][part["normalized_context_start"]:part["normalized_context_end_exclusive"]] == part["text"], "Scope is not source text")
                    for fragment in part["source_pdf_fragments"]:
                        replay.fragment(citing, fragment)
                        if key == "primary_scope_pieces":
                            primary_fragments.append(fragment)
            require(all(source_gate.marker_inside(m, primary_fragments) for m in case["citation_marker_locator"]), "Target marker outside scope")
            candidates = retrieved["candidates"]
            require(len(candidates) == 10 and retrieved["query"] == scope["prepared_query"], "Retrieval/query differs")
            for rank, evidence in enumerate(candidates, 1):
                require(evidence["source_pdf_sha256"] == pair["cited"]["sha256"]
                        and evidence["retrieval_rank"] == rank and evidence["evidence_id"] == f"D01:S{rank:02d}", "Wrong PDF/rank/evidence ID")
                require(len(evidence["pdf_fragments"]) == 1, "This prepared batch requires one raw block per evidence ID")
                fragment = evidence["pdf_fragments"][0]
                replay.fragment(cited, fragment)
                require(evidence["raw_text"] == fragment["raw_text"] and source_gate.text_sha(evidence["raw_text"]) == evidence["raw_text_sha256"], "Raw evidence changed")
                require(source_gate.text_sha(evidence["model_text"]) == evidence["model_text_sha256"], "Model evidence hash differs")
                if evidence["correction_patch_ids"]:
                    require(evidence["correction_patch_ids"] == [correction["patch_id"]]
                            and evidence["source_pdf_sha256"] == correction["source_pdf_sha256"]
                            and fragment["pdf_page"] == correction["pdf_page"]
                            and fragment["source_blocks"][0]["block_number"] == correction["block_number"]
                            and evidence["raw_text"] == raw and evidence["model_text"] == model, "Patch applied to wrong block")
                else:
                    require(evidence["raw_text"] == evidence["model_text"], "Unlogged evidence rewrite")
            require(classifier["user_prompt"] == preparation.user_prompt(scope["primary_scope_pieces"], scope["context_only_pieces"], candidates)
                    and classifier["system_prompt"] == preparation.SYSTEM_PROMPT
                    and classifier["input_sha256"] == digest({k: classifier[k] for k in ("system_prompt", "user_prompt")}), "Altered classifier payload")
            scope_hash = digest({k: scope[k] for k in ("case_id", "pair_id", "dedup_key", "primary_scope_pieces", "context_only_pieces")})
            explanation = {"claim_id": cid, "system_prompt": EXPLANATION_SYSTEM,
                           "user_prompt": classifier["user_prompt"].rsplit("\n仅对目标引用范围返回 label JSON；不能可靠判定时返回规定的 failure_status。", 1)[0]
                                          + "\n仅返回规定的证据摘录和解释 JSON，不输出分类标签。"}
            explanation["input_sha256"] = digest({k: explanation[k] for k in ("system_prompt", "user_prompt")})
            items.append({"case": case, "pair": pair, "scope": scope, "scope_sha256": scope_hash,
                          "retrieval": retrieved, "classifier": classifier, "explainer": explanation})
    finally:
        replay.close()
    files = ["preparation_summary.json"] + list(summary["generated_files_sha256"])
    return items, {name: sha(prepared / name) for name in files}


def tokenizer_for(path, dependencies=None):
    # CPU-only tokenizer code; no torch import or CUDA probing.
    import os
    os.environ.update(USE_TORCH="0", USE_TF="0", HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    if dependencies:
        sys.path.insert(0, str(Path(dependencies).resolve()))
    from transformers import AutoTokenizer
    import transformers
    require(transformers.__version__ == "5.8.0", "Tokenizer implementation must be transformers 5.8.0")
    for name, expected in preparation.TOKENIZER_FILES.items():
        require(sha(Path(path) / name) == expected, f"Official tokenizer identity differs: {name}")
    return AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)


def budget(tokenizer, record):
    text = tokenizer.apply_chat_template([{"role": "system", "content": record["system_prompt"]},
                                          {"role": "user", "content": record["user_prompt"]}],
                                         tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"]
    return {"input_tokens": len(ids), "required_total": len(ids) + MAX_NEW,
            "input_ids_sha256": hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest(),
            "within_budget": len(ids) + MAX_NEW <= MAX_LENGTH, "truncation": False}


def prepare_runtime(source, prepared, output, pdf, tokenizer):
    items, hashes = load_prepared(source, prepared, pdf)
    output = new_directory(output, source, prepared)
    rows, confirmations = [], []
    for item in items:
        cid = item["case"]["case_id"]
        stages = {s: {"input_sha256": item[s]["input_sha256"], **budget(tokenizer, item[s])} for s in ("classifier", "explainer")}
        require(stages["classifier"]["input_ids_sha256"] == item["classifier"]["expected_input_ids_sha256"], "Classifier tokens changed")
        rows.append({"case_id": cid, "pair_id": item["case"]["pair_id"], "scope_sha256": item["scope_sha256"],
                     "scope_hold": item["classifier"]["scope_hold"], "stages": stages, "released": False})
        confirmations.append({"case_id": cid, "scope_sha256": item["scope_sha256"], "confirmed": False,
                              "reviewer": None, "reviewed_at": None, "review_source": None,
                              "hold_resolution": None, "note": "Scope acknowledgement only; not semantic label or adjudication"})
    plan = {"version": VERSION, "created_at_utc": now(), "kind": "CPU_preparation_not_a_release",
            "prepared_files_sha256": hashes, "source_files_sha256": read_json(prepared / "preparation_policy_before_cpu_retrieval.json")["source_scope_files_sha256"],
            "code_sha256": code_hashes(), "code_repository": source_gate.code_provenance(), "fixed_denominator": 20, "rows": rows,
            "classifier_model": {"base": "Qwen/Qwen3.8-27B", "revision": preparation.BASE_REVISION, "adapter": "Mbio/checkpoint-100", "adapter_sha256": ADAPTER_SHA},
            "explanation_model": {"base": "Qwen/Qwen3.8-27B", "revision": preparation.BASE_REVISION, "adapter": None, "role": "independent_official_base_explainer"},
            "settings": {"max_length": MAX_LENGTH, "max_new_tokens": MAX_NEW, "enable_thinking": False, "do_sample": False, "retry_policy": "none; keep all first attempts"},
            "frozen": False, "model_loaded": False, "GPU_used": False, "human_labels_written": 0}
    write_json(output / "runtime_plan.json", plan)
    write_json(output / "scope_confirmation_template.json", {"version": VERSION, "runtime_plan_sha256": sha(output / "runtime_plan.json"), "rows": confirmations})
    write_jsonl(output / "explanation.draft.inputs.jsonl", [{**i["explainer"], "stage": "draft_not_released"} for i in items])
    write_json(output / "CPU_check_summary.json", {"fixed_points": 20, "PDF_pairs": len({i["case"]["pair_id"] for i in items}),
               "candidates_replayed": sum(len(i["retrieval"]["candidates"]) for i in items),
               "within_budget": {s: sum(r["stages"][s]["within_budget"] for r in rows) for s in ("classifier", "explainer")},
               "maximum_total_tokens": {s: max(r["stages"][s]["required_total"] for r in rows) for s in ("classifier", "explainer")},
               "scope_holds": [r["case_id"] for r in rows if r["scope_hold"]], "released": 0, "model_runs": 0,
               "formal_location_rate": None, "formal_classification_accuracy": None,
               "note": "Actual PDF and tokenizer checks, not an A100 run, human signoff or semantic acceptance"})
    return plan


def release(plan, confirmations, selected=None):
    require(plan.get("version") == VERSION and plan.get("kind") == "CPU_preparation_not_a_release"
            and plan.get("fixed_denominator") == 20 and len(plan.get("rows", [])) == 20, "Release must preserve the fixed 20-point plan")
    require(confirmations.get("runtime_plan_sha256") == digest_file_plan(plan), "Confirmation belongs to a different plan")
    rows = source_gate.keyed(plan["rows"], "case_id")
    approvals = source_gate.keyed(confirmations["rows"], "case_id", rows)
    selected = selected or list(rows)
    require(selected and len(set(selected)) == len(selected) and set(selected) <= set(rows), "Unknown/duplicate released point")
    chosen = []
    for cid in selected:
        row, approved = rows[cid], approvals.get(cid, {})
        require(approved.get("confirmed") is True and approved.get("scope_sha256") == row["scope_sha256"], f"Scope not confirmed: {cid}")
        require(all(isinstance(approved.get(k), str) and approved[k].strip() for k in ("reviewer", "reviewed_at", "review_source")), f"Scope confirmation provenance missing: {cid}")
        require(datetime.fromisoformat(approved["reviewed_at"].replace("Z", "+00:00")).tzinfo is not None, "Review time needs timezone")
        require(not row["scope_hold"] or isinstance(approved.get("hold_resolution"), str) and approved["hold_resolution"].strip(), f"Scope hold not resolved: {cid}")
        require(all(v["within_budget"] for v in row["stages"].values()), f"Input too long: {cid}")
        chosen.append(cid)
    return {"version": VERSION, "kind": "released_runtime_configuration", "created_at_utc": now(),
            "runtime_plan": plan, "runtime_plan_sha256": digest_file_plan(plan),
            "scope_confirmations": confirmations, "selected_case_ids": chosen, "fixed_denominator": 20,
            "remaining_points": [c for c in rows if c not in chosen], "model_runs_at_release": 0}


def digest_file_plan(plan):
    # Match write_json's exact bytes; the receipt is portable across OSes.
    return hashlib.sha256((json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode()).hexdigest()


def strict_json(raw):
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            require(k not in obj, "Duplicate JSON key")
            obj[k] = v
        return obj
    obj = json.loads(raw.strip(), object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    require(isinstance(obj, dict), "Response must be a single JSON object")
    return obj


def parse_classifier(raw):
    try:
        obj = strict_json(raw)
        if obj == {"failure_status": "insufficient_evidence"}:
            return {"status": "insufficient_evidence", "label": None}
        require(obj.get("label") in LABELS and "failure_status" not in obj, "Missing/invalid label or conflicting failure")
        return {"status": "valid_label", "label": obj["label"], "extra_fields_ignored": sorted(set(obj) - {"label"})}
    except (ValueError, TypeError):
        return {"status": "invalid_classifier_output", "label": None}


def parse_explanation(raw, candidates):
    try:
        obj = strict_json(raw)
        if obj == {"failure_status": "insufficient_evidence"}:
            return {"status": "insufficient_evidence", "evidence_ids": [], "reason_unreviewed": None, "quote_locators": []}
        require(set(obj) == {"evidence_ids", "quotes", "reason"}, "Wrong explanation fields")
        ids = obj["evidence_ids"]
        available = source_gate.keyed(candidates, "evidence_id")
        require(isinstance(ids, list) and ids and all(isinstance(i, str) for i in ids) and len(ids) == len(set(ids)), "Invalid/duplicate IDs")
        require(set(ids) <= set(available), "evidence_id_out_of_range")
        require(isinstance(obj["reason"], str) and obj["reason"].strip() and isinstance(obj["quotes"], list) and obj["quotes"], "Missing model reason or quotes")
        locators, covered = [], set()
        for quote in obj["quotes"]:
            require(isinstance(quote, dict) and set(quote) == {"evidence_id", "quote"} and quote["evidence_id"] in ids, "Wrong quote/ID")
            text, cid = quote["quote"], quote["evidence_id"]
            evidence = available[cid]
            require(isinstance(text, str) and text.strip() and evidence["model_text"].count(text) == 1, "quote_not_unique_verbatim")
            start = evidence["model_text"].index(text)
            fragment = evidence["pdf_fragments"][0]
            raw_quote = evidence["raw_text"][start:start + len(text)]
            locators.append({"evidence_id": cid, "model_quote": text, "raw_quote": raw_quote,
                             "raw_quote_sha256": source_gate.text_sha(raw_quote), "source_pdf_sha256": evidence["source_pdf_sha256"],
                             "pdf_page": fragment["pdf_page"], "printed_page": fragment["printed_page"],
                             "char_start": fragment["char_start"] + start, "char_end_exclusive": fragment["char_start"] + start + len(text),
                             "source_blocks": fragment["source_blocks"], "bbox_scope": source_gate.BBOX_SCOPE,
                             "offset_basis": source_gate.OFFSET_BASIS, "correction_patch_ids": evidence["correction_patch_ids"]})
            covered.add(cid)
        require(covered == set(ids), "Selected evidence lacks a quote")
        return {"status": "structure_and_quotes_valid_pending_human_semantics", "evidence_ids": ids,
                "reason_unreviewed": obj["reason"], "quote_locators": locators, "semantic_status": "pending_human_review"}
    except (ValueError, TypeError, KeyError) as error:
        return {"status": "invalid_explanation_output", "validation_error": str(error), "evidence_ids": [], "reason_unreviewed": None, "quote_locators": []}


def validate_release(released, items, hashes):
    require(released.get("version") == VERSION and released.get("kind") == "released_runtime_configuration", "Draft input not released")
    plan = released["runtime_plan"]
    require([r["case_id"] for r in plan["rows"]] == [i["case"]["case_id"] for i in items], "Released point set/order differs")
    require(release(plan, released["scope_confirmations"], released["selected_case_ids"])["selected_case_ids"] == released["selected_case_ids"], "Invalid scope release")
    require(plan["code_sha256"] == code_hashes() and plan["prepared_files_sha256"] == hashes, "Code/prepared artifacts changed after plan")
    for item, row in zip(items, plan["rows"]):
        require(item["case"]["case_id"] == row["case_id"] and item["scope_sha256"] == row["scope_sha256"], "Scope release drift")
        require(item["classifier"]["scope_hold"] == row["scope_hold"], "Original scope hold removed without a resolution record")
        require(all(row["stages"][stage]["input_sha256"] == item[stage]["input_sha256"] for stage in ("classifier", "explainer")), "Released input drift")
    return plan


def run_stage(stage, source, prepared, released_path, output, pdf, backend_factory):
    items, hashes = load_prepared(source, prepared, pdf)
    released = read_json(released_path)
    plan = validate_release(released, items, hashes)  # Before creating/loading any model.
    output = new_directory(output, source, prepared)
    selected = released["selected_case_ids"]
    keyed = {i["case"]["case_id"]: i for i in items}
    metadata = {"version": VERSION, "stage": stage, "started_at_utc": now(), "status": "running",
                "release_sha256": sha(released_path), "selected_case_ids": selected, "fixed_denominator": 20,
                "code_sha256": code_hashes(), "code_repository": plan.get("code_repository"), "settings": plan["settings"], "actual_model": None,
                "retry_policy": "none", "source_validation": "actual_PDF_replayed", "simulation": False}
    write_json(output / "run_metadata.json", metadata)
    exit_code, failed = 0, False
    try:
        with (output / "run.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                backend = backend_factory(stage, plan)
                metadata["actual_model"] = backend.identity
                metadata["simulation"] = bool(backend.identity.get("simulation"))
                write_json(output / "run_metadata.json", metadata)
                with (output / "responses.jsonl").open("w", encoding="utf-8") as responses:
                    for cid in selected:
                        item, spec = keyed[cid], next(r for r in plan["rows"] if r["case_id"] == cid)["stages"][stage]
                        response = {"case_id": cid, "input_sha256": item[stage]["input_sha256"], "raw_output": None, "attempted": False}
                        if failed:
                            response["parsed"] = {"status": "not_attempted_after_run_failure", "label": None}
                        else:
                            try:
                                response["attempted"] = True
                                raw, observed = backend.generate(item[stage], spec)
                                response.update(raw_output=raw, observed_input=observed)
                                response["parsed"] = parse_classifier(raw) if stage == "classifier" else parse_explanation(raw, item["retrieval"]["candidates"])
                            except Exception as error:
                                failed, exit_code = True, 1
                                response.update(error_type=type(error).__name__, error=str(error), parsed={"status": "inference_failed", "label": None})
                                traceback.print_exc()
                        responses.write(json.dumps(response, ensure_ascii=False) + "\n")
                        responses.flush()
                        print(cid, response["parsed"]["status"], flush=True)
            except Exception as error:
                exit_code = 1
                metadata.update(error_type=type(error).__name__, error=str(error))
                traceback.print_exc()
    finally:
        metadata.update(finished_at_utc=now(), status="finished" if exit_code == 0 else "failed", exit_code=exit_code)
        metadata["files_sha256"] = {p.name: sha(p) for p in output.iterdir() if p.is_file() and p.name != "run_metadata.json"}
        write_json(output / "run_metadata.json", metadata)
        (output / "exit_code.txt").write_text(str(exit_code) + "\n", encoding="utf-8")
    return metadata


def read_stage(directory, stage, release_sha):
    if directory is None:
        return {}, None
    directory = Path(directory)
    meta = read_json(directory / "run_metadata.json")
    require(meta["version"] == VERSION and meta["stage"] == stage and meta["release_sha256"] == release_sha, "Wrong stage or release")
    require(meta.get("status") in ("finished", "failed"), "Run not finalized; preserve partial files instead of declaring completion")
    for filename, expected in meta["files_sha256"].items():
        require(sha(source_gate.relative_file(directory, filename)) == expected, "Run artifact changed")
    rows = read_jsonl(directory / "responses.jsonl") if (directory / "responses.jsonl").exists() else []
    result = source_gate.keyed(rows, "case_id", meta["selected_case_ids"])
    identity = meta.get("actual_model")
    if identity and not meta["simulation"]:
        require(identity.get("role") == stage and identity.get("base") == "Qwen/Qwen3.8-27B"
                and identity.get("revision") == preparation.BASE_REVISION, "Actual model role/base differs")
        require(identity.get("gpu_loaded") is True and identity.get("weights_verified") is True, "Actual GPU/weight proof missing")
        require(identity.get("adapter_sha256") == (ADAPTER_SHA if stage == "classifier" else None)
                and identity.get("adapter_loaded") is (stage == "classifier"), "Actual adapter identity differs")
    return result, meta


def inspect_pair(source, prepared, citing_path, cited_path, pdf):
    """Resolve two actual PDFs to the fixed citation list; no guessed new points."""
    for role, path in (("citing", citing_path), ("cited", cited_path)):
        try:
            with pdf.open(path) as doc:
                if doc.needs_pass:
                    return {"status": "password_protected_pdf", "role": role, "model_run": False}
                if not any(page.get_text("text", sort=False).strip() for page in doc):
                    return {"status": "needs_OCR", "role": role, "model_run": False}
        except Exception as error:
            return {"status": "pdf_parse_failed", "role": role, "error": str(error), "model_run": False}
    items, _ = load_prepared(source, prepared, pdf)
    citing_sha, cited_sha = sha(citing_path), sha(cited_path)
    matched = [i for i in items if i["pair"]["citing"]["sha256"] == citing_sha and i["pair"]["cited"]["sha256"] == cited_sha]
    return {"status": "registered_pair_and_target_markers_replayed" if matched else "pair_not_in_registered_scope",
            "citing_pdf_sha256": citing_sha, "cited_pdf_sha256": cited_sha,
            "case_ids": [i["case"]["case_id"] for i in matched], "model_run": False,
            "note": "Registered PDF pairs only; unmatched PDFs need source/identity/citation registration, not a guessed label."}


def assemble(source, prepared, released_path, classifier_dir, explainer_dir, output, pdf):
    items, hashes = load_prepared(source, prepared, pdf)
    released = read_json(released_path)
    validate_release(released, items, hashes)
    classifiers, classifier_meta = read_stage(classifier_dir, "classifier", sha(released_path))
    explanations, explanation_meta = read_stage(explainer_dir, "explainer", sha(released_path))
    output = new_directory(output, source, prepared)
    rows = []
    for item in items:
        case, cid = item["case"], item["case"]["case_id"]
        c, e = classifiers.get(cid), explanations.get(cid)
        for response, stage in ((c, "classifier"), (e, "explainer")):
            if response:
                require(response["input_sha256"] == item[stage]["input_sha256"], "Response input mismatch")
                if response["raw_output"] is not None:
                    parsed = parse_classifier(response["raw_output"]) if stage == "classifier" else parse_explanation(response["raw_output"], item["retrieval"]["candidates"])
                    require(parsed == response["parsed"], "Parsed result differs from raw response")
        classifier = c["parsed"] if c else {"status": "not_run", "label": None}
        explanation = e["parsed"] if e else {"status": "not_run", "evidence_ids": [], "reason_unreviewed": None}
        identities_ok = all(meta and not meta["simulation"] and isinstance(meta.get("actual_model"), dict) and meta["actual_model"].get("gpu_loaded") is True
                            and meta["actual_model"].get("weights_verified") is True for meta in (classifier_meta, explanation_meta))
        valid = classifier["status"] == "valid_label" and explanation["status"] == "structure_and_quotes_valid_pending_human_semantics"
        engineering = bool(identities_ok and valid)
        rows.append({"case_id": cid, "pair_id": case["pair_id"], "dedup_key": case["dedup_key"], "route": case["route"], "domain": case["domain"],
                     "citing_pdf": item["pair"]["citing"], "cited_pdf": item["pair"]["cited"],
                     "citation_marker_locator": case["citation_marker_locator"], "full_context_marked": case["citing_context_marked"],
                     "scope": item["scope"], "retrieval": item["retrieval"],
                     "classifier_model": classifier_meta["actual_model"] if classifier_meta else None,
                     "explanation_model": explanation_meta["actual_model"] if explanation_meta else None,
                     "classifier_response": c, "explanation_response": e, "label": classifier.get("label"),
                     "evidence_ids": explanation.get("evidence_ids", []), "quote_locators": explanation.get("quote_locators", []),
                     "reason_unreviewed": explanation.get("reason_unreviewed"), "reason_for_display": None,
                     "confidence": None, "confidence_status": "uncalibrated", "score_support": None, "score_distort": None, "score_unrelated": None,
                     "engineering_status": "complete_technical_record_pending_human_review" if engineering else "incomplete_or_failed",
                     "engineering_success": engineering, "locator_technical_check": True, "locator_human_check": None,
                     "explanation_semantic_status": "pending_human_review", "classification_correct": None,
                     "human_review": {"李云": None, "陈明进": None, "adjudication": None},
                     "prior_annotation_exposure_note": case["prior_annotation_exposure_note"],
                     "new_model_prediction_visible": c is not None, "independent_blind_claimed": False,
                     "failure_status": [p["status"] for p in (classifier, explanation) if p["status"] not in ("valid_label", "structure_and_quotes_valid_pending_human_semantics")],
                     "formal_end_to_end_accepted": False})
    write_jsonl(output / "records.jsonl", rows)
    with (output / "records.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["case_id", "pair_id", "label", "evidence_ids", "reason_unreviewed", "reason_for_display", "engineering_status", "locator_human_check", "explanation_semantic_status", "classification_correct", "failure_status"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: source_gate.csv_safe(json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], list) else row[k]) for k in fields})
    stats = {"fixed_denominator": 20, "attempted_classifier": sum(bool(r.get("attempted")) for r in classifiers.values()),
             "attempted_explainer": sum(bool(r.get("attempted")) for r in explanations.values()),
             "engineering_success": sum(r["engineering_success"] for r in rows), "locator_human_valid": None,
             "formal_location_rate": None, "explanation_semantic_passed": None, "classification_correct": None,
             "classification_adjudicated_denominator": 0, "classification_unadjudicated": 20,
             "formal_end_to_end_accepted": 0, "note": "Four outcomes remain separate; no human review is inferred from model/format/PDF checks."}
    write_json(output / "summary.json", stats)
    return stats


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("prepare-runtime", "inspect-pair", "freeze", "run-classifier", "run-explainer", "assemble"))
    for name in ("source-root", "prepared-dir", "output-dir", "pymupdf-dir", "model-path", "tokenizer-deps", "runtime-plan", "confirmations", "release", "weights-manifest", "adapter", "classifier-run", "explainer-run", "citing-pdf", "cited-pdf"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--case-id", action="append", help="Freeze a preselected small batch; all other points remain in the denominator")
    p.add_argument("--gpu", help="Exactly one physical GPU index; required only for explicit run-* commands")
    p.add_argument("--operator", default="")
    args = p.parse_args()
    require(args.output_dir is not None, "New output directory required")
    if args.stage == "freeze":
        require(args.runtime_plan and args.confirmations and args.source_root and args.prepared_dir, "Source, prepared inputs, runtime plan and actual scope confirmations required")
        released = release(read_json(args.runtime_plan), read_json(args.confirmations), args.case_id)
        items, hashes = load_prepared(args.source_root, args.prepared_dir, source_gate.import_pdf(args.pymupdf_dir))
        validate_release(released, items, hashes)
        new_directory(args.output_dir, args.source_root, args.prepared_dir)
        write_json(args.output_dir / "release.json", released)
        print("FROZEN selected=" + str(len(released["selected_case_ids"])) + "; fixed_denominator=20; no model run")
        return 0
    require(args.source_root and args.prepared_dir, "source-root and prepared-dir required")
    pdf = source_gate.import_pdf(args.pymupdf_dir)
    if args.stage == "inspect-pair":
        require(args.citing_pdf and args.cited_pdf, "Actual citing and cited PDF paths required")
        result = inspect_pair(args.source_root, args.prepared_dir, args.citing_pdf, args.cited_pdf, pdf)
        new_directory(args.output_dir, args.source_root, args.prepared_dir)
        write_json(args.output_dir / "pair_check.json", result)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "registered_pair_and_target_markers_replayed" else 1
    if args.stage == "prepare-runtime":
        require(args.model_path, "Official tokenizer directory required")
        plan = prepare_runtime(args.source_root, args.prepared_dir, args.output_dir, pdf, tokenizer_for(args.model_path, args.tokenizer_deps))
        print("CPU_RUNTIME_PREPARATION_PASS points=20; released=0; no model run")
        return 0
    require(args.release, "Actual release file required; drafts cannot run")
    if args.stage == "assemble":
        result = assemble(args.source_root, args.prepared_dir, args.release, args.classifier_run, args.explainer_run, args.output_dir, pdf)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    require(args.model_path and args.weights_manifest and args.gpu is not None and args.operator.strip(), "Model, official weight manifest, GPU and actual operator required")
    stage = args.stage.removeprefix("run-")
    require((stage == "classifier" and args.adapter) or (stage == "explainer" and args.adapter is None), "Classifier needs Mbio; independent explainer must have no adapter")
    def factory(which, plan):
        from route1_pdf_hf_backend_v3 import HFBackend
        return HFBackend(which, plan, args.model_path, args.adapter, args.weights_manifest, args.gpu, args.operator)
    meta = run_stage(stage, args.source_root, args.prepared_dir, args.release, args.output_dir, pdf, factory)
    print("MODEL_STAGE_FINISHED status=" + meta["status"] + " exit_code=" + str(meta["exit_code"]))
    return meta["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
