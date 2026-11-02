"""CPU source replay and a single readiness ledger for the fixed PDF20 batch.

This audit does not release scopes, change inputs, run models, or sign reviews.
Run from the original local workspace; source PDFs remain outside Git.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

EXPECTED_RECORDS = "495e96f319bc49d062460f14f9c23fccb62a18427c3ac0a0c1cab821a24fd2b5"
EXPECTED_PLAN = "39b7698258b3baee1d40d6940c56b16f3d03e45ab43c37166887a9f72e9ea678"
REPO = Path(__file__).resolve().parents[2]
V3 = REPO / "results/route1_qwen38_v3/2026-10-25"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def lines(path):
    return [json.loads(s) for s in Path(path).read_text(encoding="utf-8-sig").splitlines() if s.strip()]


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8", newline="\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


FINDINGS = {
    1: ("held_by_confirmed_disposition", "背景修饰语不强行三分类；CR1不承担后续CR5及CR6/7数量主张。", "保留固定点，待共同确定非三分类终态。"),
    2: ("already_run_review_pending", "PDB总结构数与独特蛋白质结构数不能直接比较。", "沿用首批双方来文，补共同裁决。"),
    3: ("already_run_review_pending", "核心修剪功能、popular限定与理由合格性分别处理。", "补双方逐项意见，解析修订另行确认。"),
    4: ("already_run_review_pending", "功能整合支持与原模型理由过严问题已有回复。", "导入有来源的双方意见，保留未决项。"),
    5: ("already_run_review_pending", "最早症状起始日期不能充当病原体鉴定日期。", "按原句时间谓词完成语义裁决。"),
    6: ("already_run_review_pending", "新型、RNA和分类群证据不能替代未召回的包膜属性。", "不自动采用外部常识豁免，保留候选边界。"),
    7: ("text_revision_proposed_not_applied", "保留来源假说及人与人传播的复合主张；修复trans mission转写。", "确认映射修订后重建对应输入及预算。"),
    8: ("scope_revision_proposed_not_applied", "方法名词短语缺少上文improved ability等主谓结构。", "确认主范围与背景角色后重建输入；不继承同句其他文献主张。"),
    9: ("keep_scope_proposed", "未来可能增加X与已经验证、固定采用某个X不同。", "保留原范围及指代背景，等待范围确认。"),
    10: ("candidate_coverage_review_pending", "旧候选含表格碎片和参考文献；A−T+不能用总体tau阳性比例替代。", "共同核对候选覆盖及图注冲突；补充全文不冒充原候选。"),
    11: ("context_revision_proposed_not_applied", "This bioinformatics approach缺少前文指代。", "确认增加背景后重算query、检索及两个阶段预算。"),
    12: ("text_revision_proposed_not_applied", "旧规范化删除SARS词内连字符。", "保留原PDF连字符，重建映射和对应输入。"),
    13: ("scope_and_coverage_review_pending", "区分生物标志物分组与六级临床分期；被引第9页明确不蕴含固定顺序或因果。", "建议保留原复合主张，并加入后句biomarker profile澄清背景；不代填标签。"),
    14: ("context_and_numeric_review_pending", "进展到痴呆与MCI的HR不同；施引1.5/5.6/39.9与当前被引PDF1.6/6.2/41.3存在版本或口径待核。", "建议加入终点及参考组背景，核对来源版本/模型后再裁决，不静默改数字。"),
    15: ("held_by_confirmed_disposition", "PDB资源身份引用；训练行为与下载日期是施引作者自述。", "保留固定点，资源身份核对与三分类分开。"),
    16: ("text_and_attribution_review_pending", "high-throughput被规范化为highthroughput；本文病例定义与被引研究所述样本来源不可混同。", "确认词形映射修订并核对引用归属；不由方法名称相同推定整句受支持。"),
    17: ("keep_scope_proposed", "2018六级临床分期与AT(N)生物分组不同；S10明确1–6，S09只有表题。", "保留原范围；表6正文仅作补充核对，不充当既有候选全文。"),
    18: ("keep_scope_proposed", "临床特征类似不是两种疾病完全相同，也不承担后文死亡率主张。", "保留当前引用组及作者本研究/前人结果的归属，等待范围确认。"),
    19: ("keep_scope_proposed", "保留(N)非AD特异与A/T对比；后续取消括号属于新修订。", "保留当前范围，候选S01/S05可供人工核对。"),
    20: ("qualifier_coverage_review_pending", "common及some cases severe需分别核对；当前S06说明常见，不能由此直接补出severe。", "保留复合限定与两个引用；不合并同段死亡率引用点或强填三分类。"),
}

PRIOR = {
    7: "point07_scope_preparation_2026-10-23",
    8: "point08_scope_preparation_2026-10-23",
    9: "point09_scope_preparation_2026-10-23",
    10: "point10_scope_coverage_preparation_2026-10-23",
    11: "point11_scope_anaphora_preparation_2026-10-23",
    12: "point12_scope_transcription_preparation_2026-10-23",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    root, out = args.workspace.resolve(), args.output_dir.resolve()
    source = root / "10.19-11.2/路线一PDF独立清单_20261020"
    run = root / "10.19-11.2/A100_PDF首批5点资源修订_20261022/route1_pdf_first5_20261022_resource_run01"
    demo = V3 / "pdf_demo"
    original = run / "assembled/records.jsonl"
    plan_path = demo / "first5_A100_2026-10-22/runtime_plan.original.json"
    confirmation_path = root / "10.19-11.2/A100_PDF首批5点执行_20261021/route1_pdf_first5_20261021/scope_confirmations.json"
    inputs_path = demo / "scope_and_input_preparation_2026-10-20/classification.draft.inputs.jsonl"
    corrections_path = demo / "scope_and_input_preparation_2026-10-20/text_layer_corrections.json"
    require(not out.exists(), "Output exists: choose a new dated revision")
    require(sha(original) == EXPECTED_RECORDS, "Original assembled record hash differs")
    require(sha(plan_path) == EXPECTED_PLAN, "Original A100 plan hash differs")
    rows, cases, plans = lines(original), lines(source / "case_manifest.jsonl"), read(plan_path)
    confirmations = read(confirmation_path)
    require(len(rows) == len(cases) == len(plans["rows"]) == len(confirmations["rows"]) == 20, "Fixed20 incomplete")
    require([x["case_id"] for x in rows] == [x["case_id"] for x in cases] == [x["case_id"] for x in plans["rows"]] == [x["case_id"] for x in confirmations["rows"]], "Case order differs")
    require(len({x["dedup_key"] for x in rows}) == 20, "Physical citation deduplication failed")
    require(len({x["pair_id"] for x in rows}) == 10, "Pair set changed")
    protected = [p for p in run.rglob("*") if p.is_file()]
    protected += [plan_path, confirmation_path, inputs_path, corrections_path, source / "case_manifest.jsonl", source / "pair_manifest.jsonl", source / "scope_lock.json"]
    for name in ("run_route1_pdf_v3.py", "prepare_pdf20_scope_inputs_20261020.py", "build_sarol_inputs_v2.py"):
        p = REPO / "code/ly" / name
        require(sha(p) == plans["code_sha256"][name], f"Frozen code differs: {name}")
        protected.append(p)
    for row in rows:
        for role in ("citing_pdf", "cited_pdf"):
            protected.append(source / row[role]["relative_path"])
    before = {str(p): sha(p) for p in protected}
    sys.path.insert(0, str(REPO / "code/ly"))
    import run_route1_pdf_v3 as gate
    import prepare_pdf20_scope_inputs_20261020 as prep
    pdf = gate.import_pdf(root / "tmp/pdf_locator_deps")
    replay = gate.PdfReplay(pdf)
    drafts = {x["claim_id"]: x for x in lines(inputs_path)}
    recorded_correction = read(corrections_path)
    ledger, checks, supplements = [], [], []
    patch_counts = Counter()

    def fragment(document, page_no, start, end):
        page = document[page_no - 1]
        text, boxes, cursor = page.get_text("text", sort=False), [], 0
        require(0 <= start < end <= len(text), "Bad supplementary span")
        for number, block in enumerate(page.get_text("blocks", sort=False), 1):
            if len(block) > 6 and block[6] != 0:
                continue
            bstart = text.find(str(block[4]), cursor)
            require(bstart >= 0, "Supplement block mapping failed")
            cursor = bstart + len(str(block[4]))
            if bstart < end and start < cursor:
                boxes.append({"block_number": number, "bbox": [round(float(z), 3) for z in block[:4]]})
        f = {"pdf_page": page_no, "printed_page": None, "char_start": start, "char_end_exclusive": end,
             "raw_text": text[start:end], "raw_text_sha256": text_sha(text[start:end]),
             "source_blocks": boxes, "offset_basis": gate.OFFSET_BASIS, "bbox_scope": gate.BBOX_SCOPE}
        replay.fragment(document, f)
        return f

    def supplement(number, role, page_no, pattern, key, note):
        row = rows[number - 1]
        document = replay.open(source, row[role])
        page = document[page_no - 1].get_text("text", sort=False)
        match = re.search(pattern, page, flags=re.S)
        require(match is not None, f"Supplement anchor missing: {key}")
        f = fragment(document, page_no, *match.span())
        spans = sorted((x["char_start"], x["char_end_exclusive"]) for c in row["retrieval"]["candidates"] for x in c["pdf_fragments"] if x["pdf_page"] == page_no) if role == "cited_pdf" else []
        cursor = f["char_start"]
        for left, right in spans:
            if left <= cursor < right:
                cursor = max(cursor, right)
        covered = role == "cited_pdf" and cursor >= f["char_end_exclusive"]
        value = {"case_id": row["case_id"], "point_number": number, "key": key, "pdf_role": role,
                 "source_pdf_sha256": row[role]["sha256"], "fragment": f,
                 "fully_covered_by_frozen_candidates": covered if role == "cited_pdf" else None,
                 "added_to_model_input": False, "note": note}
        supplements.append(value)
        return value

    for number, (row, case, plan, confirmed) in enumerate(zip(rows, cases, plans["rows"], confirmations["rows"]), 1):
        citing, cited = replay.open(source, row["citing_pdf"]), replay.open(source, row["cited_pdf"])
        for field in ("citing_context_raw_fragments", "citation_group_locator", "reference_pdf_title_locator"):
            for f in case[field]:
                replay.fragment(citing, f)
        for f in row["citation_marker_locator"]:
            replay.fragment(citing, f)
        normalized, _ = prep.normalized_with_map(case["citing_context_raw_fragments"])
        require(normalized == case["citing_context"], f"Source normalization differs: {number}")
        scope = row["scope"]
        require(scope["dedup_key"] == row["dedup_key"] == case["dedup_key"], "Dedup key differs")
        for field in ("primary_scope_pieces", "context_only_pieces"):
            for piece in scope[field]:
                require(normalized[piece["normalized_context_start"]:piece["normalized_context_end_exclusive"]] == piece["text"], f"Normalized span differs: {number}")
                for f in piece["source_pdf_fragments"]:
                    replay.fragment(citing, f)
        keys = ("case_id", "pair_id", "dedup_key", "primary_scope_pieces", "context_only_pieces")
        scope_sha = text_sha(json.dumps({k: scope[k] for k in keys}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        require(scope_sha == plan["scope_sha256"] == confirmed["scope_sha256"], f"Scope hash differs: {number}")
        candidate_checks = []
        for c in row["retrieval"]["candidates"]:
            raw = "".join(replay.fragment(cited, f) for f in c["pdf_fragments"])
            require(raw == c["raw_text"] and text_sha(raw) == c["raw_text_sha256"], f"Candidate raw differs: {number}")
            require(text_sha(c["model_text"]) == c["model_text_sha256"], "Model text hash differs")
            require(c["source_pdf_sha256"] == row["cited_pdf"]["sha256"], "Wrong candidate PDF")
            require(raw == c["model_text"] or bool(c["correction_patch_ids"]), "Unrecorded candidate correction")
            if raw != c["model_text"]:
                require(c["correction_patch_ids"] == [recorded_correction["patch_id"]]
                        and raw == recorded_correction["raw_text"]
                        and c["source_pdf_sha256"] == recorded_correction["source_pdf_sha256"], "Candidate correction does not match the archived patch")
                changed = list(raw)
                for patch in recorded_correction["patches"]:
                    position = patch["within_block_index"]
                    require(changed[position] == patch["before"], "Correction source character differs")
                    changed[position] = patch["after"]
                require("".join(changed) == c["model_text"] == recorded_correction["model_text"], "Recorded correction does not reproduce model text")
            patch_counts.update(c["correction_patch_ids"])
            candidate_checks.append({"evidence_id": c["evidence_id"], "raw_text_sha256": c["raw_text_sha256"],
                                     "model_text_sha256": c["model_text_sha256"], "correction_patch_ids": c["correction_patch_ids"], "source_span_and_bbox_replayed": True})
        require(len(candidate_checks) == 10, "Frozen top10 count differs")
        prompt = prep.user_prompt(scope["primary_scope_pieces"], scope["context_only_pieces"], row["retrieval"]["candidates"])
        draft = drafts[row["case_id"]]
        require(prompt == draft["user_prompt"] and gate.model_input_sha256(prep.SYSTEM_PROMPT, prompt) == draft["input_sha256"] == plan["stages"]["classifier"]["input_sha256"], f"Classifier input differs: {number}")
        for stage in plan["stages"].values():
            require(stage["required_total"] == stage["input_tokens"] + 512 <= 5120 and not stage["truncation"], "Original recorded budget is invalid")
        status, issue, action = FINDINGS[number]
        ran = row["classifier_response"] is not None
        require(ran == (number in (2, 3, 4, 5, 6)), "Unexpected actual-run set")
        if not ran:
            require(row["explanation_response"] is None and row["label"] is None, "Unrun row carries a new result")
        require(not row["formal_end_to_end_accepted"], "Original acceptance set differs")
        prior = f"../{PRIOR[number]}/" if number in PRIOR else None
        if number in PRIOR:
            require((demo / PRIOR[number]).is_dir(), "Prior case evidence index missing")
        ledger.append({"point_number": number, "case_id": row["case_id"], "pair_id": row["pair_id"],
                       "dedup_key": row["dedup_key"], "citing_pmcid": row["citing_pdf"]["pmcid"], "cited_pmcid": row["cited_pdf"]["pmcid"],
                       "reference_id": scope["target_reference_id"], "source_pdf_sha256": {k: row[k]["sha256"] for k in ("citing_pdf", "cited_pdf")},
                       "primary_scope_text": " ".join(p["text"] for p in scope["primary_scope_pieces"]),
                       "scope_sha256": scope_sha, "scope_confirmation_as_recorded": confirmed,
                       "scope_hold": plan["scope_hold"], "actual_classifier_run": ran, "actual_explainer_run": row["explanation_response"] is not None,
                       "original_strict_engineering_success": row["engineering_success"],
                       "readiness_status": status, "assistant_source_check_note": issue, "next_action": action,
                       "prior_evidence_index": prior, "new_source_evidence_file": "source_diagnostics.jsonl" if number in (13, 14, 16, 17, 18, 19, 20) else None,
                       "current_active_classifier_input_sha256": draft["input_sha256"], "recorded_token_budget": plan["stages"],
                       "li_review": None, "chen_review": None, "joint_adjudication": None,
                       "human_review_note": "Blank means no signed review imported here. Previously received opinions and scope approvals remain in linked originals.",
                       "formal_locator_valid": None, "formal_explanation_semantic_passed": None, "formal_classification_correct": None,
                       "formal_end_to_end_accepted": False, "new_label": None, "active_input_modified": False, "new_scope_release": False})
        checks.append({"point_number": number, "case_id": row["case_id"], "scope_sha256": scope_sha,
                       "source_context_marker_reference_and_scope_replayed": True, "original_classifier_input_reproduced": True,
                       "candidate_checks": candidate_checks})

    supplement(13, "cited_pdf", 9, r"Although the term.*?causality\.", "biomarker_profiles_do_not_imply_sequence", "不把生物分组当作确定的演进顺序；原候选是否包含此句见覆盖字段。")
    supplement(13, "citing_pdf", 11, r"However, in 2018 we used the term biomarker profile.*?clinical staging\.", "citing_profile_clarification", "建议背景范围，仅保存原PDF文本，不改当前主范围。")
    supplement(14, "cited_pdf", 4, r"A\+TNEO-T.*?P\u2009=\u20090\.53\)\.", "dementia_hazard_ratios", "对应全因痴呆，不与MCI风险比混用；数值差异先核来源版本。")
    supplement(14, "cited_pdf", 8, r"First, we examined progression.*?reference group\.", "cox_endpoint_and_reference", "当前PDF说明Cox模型、终点、调整变量与参考组；不凭meta-analysis称谓直接判错。")
    supplement(14, "citing_pdf", 14, r"Specifically,.*?\(stages C and D in our scheme", "citing_dementia_endpoint_context", "建议保留终点与参考组背景，数字不静默替换。")
    high_throughput = supplement(16, "citing_pdf", 2, r"high-\nthroughput", "lexical_high_throughput_hyphen", "拟保留词内连字符，旧规范化确为highthroughput；修订未应用。")
    require(prep.normalize(high_throughput["fragment"]["raw_text"]) == "highthroughput", "Old lexical-hyphen loss was not reproduced")
    supplement(16, "cited_pdf", 9, r"study has some limitations\. First, for most of the.*?difference in the\s+viral RNA detection rate between upper and lower\s+respiratory tract specimens\.", "cohort_specimen_attribution_limit", "这里只核文献归属及范围差异，不复制实验操作参数。")
    supplement(17, "cited_pdf", 16, r"It is apparent that numeric stages 1–6.*?disease-specific AD biomarkers\.", "six_numeric_clinical_stages", "S10已有此陈述；不可与第13点生物分组演进混同。")
    supplement(17, "cited_pdf", 53, r"Table 6\s+Numeric clinical staging—Applicable only to individuals in the Alzheimer’s continuum", "table6_heading", "仅表题不代表模型看到了完整六行。")
    supplement(18, "cited_pdf", 8, r"Similarities of clinical features.*?infections\.20,21", "limited_clinical_resemblance", "支持范围仍须人工判断；类似不等于完全一致。")
    supplement(19, "cited_pdf", 38, r"A and T indicate specific.*?parentheses\.", "specificity_parentheses", "对应2018括号用法，未自动赋予分类标签。")
    supplement(20, "cited_pdf", 2, r"26 \(63%\) of 41 patients had lymphopenia\.", "lymphopenia_frequency", "频率句不能自动承担some cases severe限定。")
    require("torch" not in sys.modules, "CPU audit unexpectedly imported torch")
    unique_pdfs = len(replay.documents)
    replay.close()
    require(all(sha(p) == value for p, value in before.items()), "A protected source changed during the audit")
    out.mkdir(parents=True)
    jsonl(out / "point_readiness.jsonl", ledger)
    jsonl(out / "source_replay_checks.jsonl", checks)
    jsonl(out / "source_diagnostics.jsonl", supplements)
    summary = {"version": "route1_pdf20_weekly_readiness_20261023", "status": "CPU_SOURCE_REPLAY_PASS_FORMAL_DELIVERY_INCOMPLETE",
               "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "timestamp_meaning": "Automated audit time, not human review time",
               "fixed_points": 20, "pairs": 10, "unique_pdfs_verified": unique_pdfs, "candidate_records_replayed": sum(len(x["candidate_checks"]) for x in checks),
               "original_classifier_inputs_reproduced": len(checks), "recorded_two_stage_budgets_checked": 40,
               "new_tokenization_performed": False, "candidate_correction_patch_counts_as_recorded": dict(patch_counts),
               "scope_approved_as_recorded": sum(x["confirmed"] for x in confirmations["rows"]),
               "held_by_confirmed_disposition": 2, "other_scopes_not_released": 13,
               "actual_classifier_points": sum(x["actual_classifier_run"] for x in ledger),
               "actual_explainer_points": sum(x["actual_explainer_run"] for x in ledger),
               "original_strict_engineering_success": sum(x["original_strict_engineering_success"] for x in ledger),
               "formal_location_rate": None, "formal_explanation_semantic_rate": None, "formal_classification_correct": None,
               "formal_end_to_end_accepted": 0, "new_scope_approvals": 0, "new_model_runs": 0,
               "new_human_reviews_imported": 0, "historical_human_opinions_not_erased": True,
               "original_files_unchanged": True, "protected_files_sha256": before,
               "source_records_sha256": EXPECTED_RECORDS, "source_A100_plan_sha256": EXPECTED_PLAN,
               "audit_script_sha256": sha(__file__),
               "model_loaded": False, "inference_performed": False, "GPU_used": False, "torch_imported": False}
    write(out / "summary.json", summary)
    write(out / "files_sha256.json", {p.name: sha(p) for p in out.iterdir() if p.is_file()})
    print(f"PDF20_SOURCE_REPLAY_PASS points=20 pairs=10 pdfs={unique_pdfs} candidates=200 original_inputs=20")
    print("ACTUAL_RUNS_UNCHANGED classifier=5 explainer=5 strict_engineering=1 formal_accepted=0")
    print("model_loaded=false input_changed=false human_signoff_added=false")
    print(f"output={out}")


if __name__ == "__main__":
    main()
