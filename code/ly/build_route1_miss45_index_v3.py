"""Build a traceable review index from frozen v2 predictions; no inference."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")
REPO = Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def text_sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def js(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def dump_rows(path, rows):
    path.write_text("".join(js(row)+"\n" for row in rows), encoding="utf-8")

def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def indexed(path, key="claim_id"):
    rows = read_rows(path)
    keys = [str(row[key]) for row in rows]
    assert all(k and k != "None" for k in keys)
    assert len(keys) == len(set(keys)), f"Duplicate key in {path}"
    return rows, dict(zip(keys, rows))

def score(gold, pred):
    matrix = {g: dict.fromkeys((*LABELS, "INVALID"), 0) for g in LABELS}
    for cid, row in gold.items():
        p = pred[cid]["pred"]
        assert p in (*LABELS, "INVALID")
        assert pred[cid]["gold"] == row["label"]
        assert pred[cid]["attempt"] == 1 and pred[cid]["retry_count"] == 0
        matrix[row["label"]][p] += 1
    n = len(gold)
    return {"n": n, "correct": sum(matrix[g][g] for g in LABELS),
            "invalid": sum(matrix[g]["INVALID"] for g in LABELS),
            "confusion_matrix": matrix,
            "not_accurate_support": sum(matrix["NOT_ACCURATE"].values()),
            "not_accurate_true_positive": matrix["NOT_ACCURATE"]["NOT_ACCURATE"],
            "not_accurate_to_accurate": matrix["NOT_ACCURATE"]["ACCURATE"]}

def prepare(args):
    repo, out = args.repo_root, args.output_dir
    if (out / "miss45_review.csv").exists():
        raise RuntimeError("miss45_review.csv already exists; use a fresh output directory to preserve human edits")
    out.mkdir(parents=True, exist_ok=True)
    args.tables_json.parent.mkdir(parents=True, exist_ok=True)
    data = repo / "results/route1_qwen38_v2/2026-10-15"
    run = repo / "results/route1_qwen38_v2/2026-10-19/test_refreeze5120_run02/test"
    paths = {
        "sarol_inputs": data / "sarol/test.inputs.jsonl",
        "sarol_gold": data / "sarol/test.gold.jsonl",
        "sarol_M0": run / "sarol/M0/M0_test_predictions.jsonl",
        "sarol_Mbio": run / "sarol/Mbio/Mbio_test_predictions.jsonl",
        "sarol_corpus": repo / "data/quality_v1/sarol/corpus.jsonl",
        "sciciteval_gold": data / "sciciteval/test.gold.jsonl",
        "sciciteval_M0": run / "sciciteval/M0/M0_test_predictions.jsonl",
        "sciciteval_Mscv": run / "sciciteval/Mscv/Mscv_test_predictions.jsonl",
        "prior_paired_rows": repo / "results/route1_qwen38_v2/2026-10-19/test_paired_analysis/paired_rows.jsonl",
        "review20": args.review20,
    }
    expected = {
        "sarol_inputs": "46b441cd7623ca827113ba5a52ae8a08d34cbbc4d5211b133e6af8595fc27391",
        "sarol_gold": "696d6d9290c03e3ca79ff705aeeab52161932f3c2b229db87298427e900caeae",
        "sarol_M0": "bdcabeff68aa28e9cabe76f7bbda771958dcf0cd5edf8b88dfcad13a7ca2408f",
        "sarol_Mbio": "e61218ea91fd2cba670bfa44ae0bb5c7ccd32dd00da964751de89d7f80601e2d",
        "sarol_corpus": "0d60d3addf7b450d7291fd1c68d27ab6e5b8b38c177f374ae2cce5bb1a2885d3",
    }
    for key, h in expected.items(): assert sha(paths[key]) == h, key
    # Corroborate the model outputs against the separately downloaded A100 run.
    download = repo.parent / "route1_test_run02_20261019/test/sarol"
    download_check = {}
    for model in ("M0", "Mbio"):
        p = download / model / f"{model}_test_predictions.jsonl"
        if p.exists():
            assert sha(p) == sha(paths["sarol_"+model])
            download_check[model] = sha(p)

    gold_rows, gold = indexed(paths["sarol_gold"])
    input_rows, inputs = indexed(paths["sarol_inputs"])
    m0_rows, m0 = indexed(paths["sarol_M0"])
    mb_rows, mb = indexed(paths["sarol_Mbio"])
    assert len(gold) == len(inputs) == len(m0) == len(mb) == 606
    assert list(gold) == list(inputs) == list(m0) == list(mb)
    assert Counter(r["label"] for r in gold_rows) == {"ACCURATE":386,"NOT_ACCURATE":170,"IRRELEVANT":50}
    corp_rows, corpus = indexed(paths["sarol_corpus"], "doc_id")
    review_rows, prior = indexed(paths["review20"], "case_id")
    assert len(prior) == 20
    old_pairs = {(r["dataset"],str(r["claim_id"])):r for r in read_rows(paths["prior_paired_rows"])}
    for cid in gold:
        assert old_pairs[("sarol",cid)]["gold"] == gold[cid]["label"]
        assert old_pairs[("sarol",cid)]["predictions"]["M0"] == m0[cid]["pred"]
        assert old_pairs[("sarol",cid)]["predictions"]["Mbio"] == mb[cid]["pred"]
    review_source = out / "prior_review"
    review_source.mkdir(exist_ok=True)
    copied_review = review_source / "review20_final.jsonl"
    if paths["review20"].resolve() != copied_review.resolve():
        shutil.copyfile(paths["review20"], copied_review)
    assert sha(copied_review) == sha(paths["review20"])

    paired, payload, review = [], [], []
    repairs, regressions = Counter(), Counter()
    selection = []
    for line_no, (cid, g) in enumerate(gold.items(), 1):
        a, b = m0[cid], mb[cid]
        correct_a, correct_b = a["pred"] == g["label"], b["pred"] == g["label"]
        fixed = not correct_a and correct_b
        new_error = correct_a and not correct_b
        if fixed: repairs[g["label"]] += 1
        if new_error: regressions[g["label"]] += 1
        selected = g["label"] == "NOT_ACCURATE" and a["pred"] == "NOT_ACCURATE" and b["pred"] == "ACCURATE"
        paired.append({"case_id":f"sarol:test:{cid}","dataset":"sarol","split":"test","claim_id":cid,
                       "gold":g["label"],"M0_pred":a["pred"],"Mbio_pred":b["pred"],
                       "M0_correct":correct_a,"Mbio_correct":correct_b,"repaired":fixed,"new_error":new_error,
                       "is_miss45":selected,"M0_invalid_reason":a["invalid_reason"] or "",
                       "Mbio_invalid_reason":b["invalid_reason"] or "","frozen_input_sha256":inputs[cid]["input_sha256"],
                       "source_line_number":line_no})
        if not selected: continue
        inp, case_id = inputs[cid], f"sarol:test:{cid}"
        assert len(inp["candidate_evidence"]) == 10
        assert set(inp["allowed_evidence_ids"]) == {e["evidence_id"] for e in inp["candidate_evidence"]}
        candidate_keys = {(str(e["doc_id"]),int(e["sentence_id"])) for e in inp["candidate_evidence"]}
        gold_spans = []
        for did, groups in g["gold_evidence"].items():
            assert str(did) in corpus
            for group in groups:
                for sid in group["sentences"]:
                    assert isinstance(sid,int) and 0 <= sid < len(corpus[str(did)]["abstract"])
                    text = corpus[str(did)]["abstract"][sid]
                    inside = (str(did),sid) in candidate_keys
                    gold_spans.append({"doc_id":str(did),"sentence_id":sid,"sentence_index_basis":"zero-based source corpus abstract array",
                                       "annotation_label":group["label"],"text":text,"text_sha256":text_sha(text),
                                       "in_original_model_input":inside,
                                       "scope_note":"original candidate includes this source sentence" if inside else "diagnostic gold-reference sentence; original model input did not include it"})
        reused = prior.get(case_id)
        if reused:
            assert reused["user_prompt"] == inp["user_prompt"]
            assert reused["candidate_evidence"] == inp["candidate_evidence"]
        ordinal = len(payload)+1
        full = {"case_id":case_id,"dataset":"sarol","split":"test","claim_id":cid,
                "selection_rule":"frozen_gold=NOT_ACCURATE and M0_pred=NOT_ACCURATE and Mbio_pred=ACCURATE",
                "source_line_number":line_no,"original_model_input":inp,
                "M0_original_prediction":a,"Mbio_original_prediction":b,"frozen_gold_record":g,
                "gold_reference_spans_diagnostic_only":gold_spans,
                "prior_review20_record":reused,
                "new_human_review_performed":False,"automatic_error_reason_codes_assigned":False}
        payload.append(full)
        li = reused["liyun_original_review"] if reused else {}
        chen = reused["chen_mingjin_original_review"] if reused else {}
        row = {"index":ordinal,"case_id":case_id,"dataset":"sarol","split":"test","claim_id":cid,
               "gold":g["label"],"M0_pred":a["pred"],"Mbio_pred":b["pred"],
               "claim_text":inp["user_prompt"].split("\n候选证据：",1)[0].removeprefix("引用论断："),
               "payload_path":"miss45_payload.jsonl","payload_line":ordinal,
               "frozen_input_sha256":inp["input_sha256"],"source_line_number":line_no,
               "gold_evidence_missing":g["evidence_missing"],"gold_reference_count":len(gold_spans),
               "gold_reference_not_in_input_count":sum(not s["in_original_model_input"] for s in gold_spans),
               "review20_reused":bool(reused),"review_mode":"non_blind_prediction_visible",
               "li_label":li.get("label_judgment", ""),"li_evidence_ids":js(li["evidence_ids"]) if li else "",
               "li_reason":li.get("reason", ""),"li_review_date":li.get("review_date", ""),
               "li_prediction_seen":"unknown_from_prior_record" if reused else "",
               "li_reason_codes":"","li_sem_subtypes":"","li_attribution_basis":"",
               "chen_label":chen.get("label_judgment", ""),"chen_evidence_ids":js(chen["evidence_ids"]) if chen else "",
               "chen_reason":chen.get("reason", ""),"chen_review_date":chen.get("review_date", ""),
               "chen_prediction_seen":"unknown_from_prior_record" if reused else "",
               "chen_reason_codes":"","chen_sem_subtypes":"","chen_attribution_basis":"",
               "resolved_label":reused["final_label"] if reused else "",
               "resolved_reason":reused["final_reason"] if reused else "",
               "reason_codes":"","sem_subtypes":"","attribution_basis":"","attribution_evidence_path":"",
               "gold_question_status":"not_reviewed_for_this_week",
               "review_status":"prior_label_review_reused_reason_codes_pending" if reused else "pending_two_reviews"}
        review.append(row)
        selection.append(cid)
    assert len(selection) == len(set(selection)) == 45
    assert sum(repairs.values()) == 186 and sum(regressions.values()) == 51
    assert repairs == {"ACCURATE":177,"NOT_ACCURATE":9}
    assert regressions == {"NOT_ACCURATE":45,"IRRELEVANT":6}
    sm0, smb = score(gold,m0), score(gold,mb)
    assert (sm0["correct"],smb["correct"],sm0["invalid"],smb["invalid"]) == (299,434,1,0)
    assert (sm0["not_accurate_true_positive"],smb["not_accurate_true_positive"]) == (132,96)
    assert (sm0["not_accurate_to_accurate"],smb["not_accurate_to_accurate"]) == (24,71)
    two_from_irrelevant = [cid for cid in gold if gold[cid]["label"] == "NOT_ACCURATE" and m0[cid]["pred"] == "IRRELEVANT" and mb[cid]["pred"] == "ACCURATE"]
    nine_repairs = [cid for cid in gold if gold[cid]["label"] == "NOT_ACCURATE" and m0[cid]["pred"] != "NOT_ACCURATE" and mb[cid]["pred"] == "NOT_ACCURATE"]
    assert len(two_from_irrelevant) == 2 and len(nine_repairs) == 9
    overlap = [r["case_id"] for r in review if r["review20_reused"]]
    assert overlap == ["sarol:test:51"]
    assert sum(r["gold_evidence_missing"] for r in review) == 10

    _, sg = indexed(paths["sciciteval_gold"])
    _, sa = indexed(paths["sciciteval_M0"])
    _, sb = indexed(paths["sciciteval_Mscv"])
    assert set(sg) == set(sa) == set(sb) and len(sg) == 257
    sci_fixed = sum(sa[c]["pred"] != sg[c]["label"] and sb[c]["pred"] == sg[c]["label"] for c in sg)
    sci_new = sum(sa[c]["pred"] == sg[c]["label"] and sb[c]["pred"] != sg[c]["label"] for c in sg)
    s0, s1 = score(sg,sa), score(sg,sb)
    assert (sci_fixed,sci_new,s0["not_accurate_true_positive"],s1["not_accurate_true_positive"]) == (19,9,52,67)

    dump_rows(out/"miss45_payload.jsonl",payload)
    dump_rows(out/"review20_overlap.jsonl",[r for r in review_rows if r["case_id"] in overlap])
    (out/"gold_questions_sidecar.jsonl").write_text("",encoding="utf-8")
    stats = {"status":"index_generated_human_attribution_pending","date":"2026-10-20",
             "sarol":{"n":606,"M0":sm0,"Mbio":smb,"repaired":186,"new_errors":51,"net_correct_gain":135,
                      "repairs_by_gold":dict(repairs),"new_errors_by_gold":dict(regressions),
                      "miss45_ids":selection,"miss45_count":45,"recall_true_positive_drop":36,
                      "not_accurate_repairs_ids":nine_repairs,"not_accurate_repairs_count":9,
                      "not_accurate_to_accurate_net_increase":47,
                      "extra_two_originally_irrelevant_ids":two_from_irrelevant},
             "sciciteval_Mscv_vs_M0":{"n":257,"repaired":sci_fixed,"new_errors":sci_new,
                                       "not_accurate_support":89,"M0_not_accurate_true_positive":52,"Mscv_not_accurate_true_positive":67},
             "review20_overlap_case_ids":overlap,"prior_label_review_reused":1,"new_cases_pending_two_reviews":44,
             "reason_code_reviews_pending":45,"gold_evidence_missing_in_selected":10,
             "diagnostic_gold_sentence_reference_occurrences":sum(r["gold_reference_count"] for r in review),
             "gold_sentence_reference_occurrences_not_in_original_input":sum(r["gold_reference_not_in_input_count"] for r in review),
             "gold_question_sidecar_status":"empty_initial_template; gold-question assessment still pending",
             "model_inference_performed":False,"frozen_test_metrics_or_gold_changed":False}
    dump(out/"paired_summary.json",stats)
    sources = {k:{"path":str(p.resolve()),"repo_relative_path":p.relative_to(repo).as_posix() if p.is_relative_to(repo) else None,"sha256":sha(p)} for k,p in paths.items()}
    commit = subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()
    source_manifest = {"generation_date":"2026-10-20","source_repo_commit":commit,
                       "generator_commit":None,"generator_file_sha256":sha(Path(__file__)),
                       "source_files":sources,"separate_A100_download_hash_checks":download_check,
                       "review20_archived_copy":"prior_review/review20_final.jsonl",
                       "review20_archived_sha256":sha(copied_review),
                       "join_key":["dataset","split","claim_id"],
                       "order":"unchanged frozen Sarol Test input/gold order; line numbers 1-based",
                       "new_human_fields":"blank except verbatim reuse of the single overlapping case"}
    dump(out/"source_manifest.json",source_manifest)
    dump(args.tables_json,{"output_dir":str(out.resolve()),"tables":[
        {"sheet":"45条漏检复核","file":"miss45_review.csv","columns":list(review[0]),"rows":[list(r.values()) for r in review]},
        {"sheet":"Sarol606配对","file":"paired_transitions.csv","columns":list(paired[0]),"rows":[list(r.values()) for r in paired]}]})
    print(js({"phase":"prepare","selected":45,"reused":overlap,"new_reviews_pending":44,"tables_json":str(args.tables_json)}))

def finalize(args):
    out = args.output_dir
    stats = json.loads((out/"paired_summary.json").read_text(encoding="utf-8"))
    payload = read_rows(out/"miss45_payload.jsonl")
    with (out/"miss45_review.csv").open(encoding="utf-8-sig",newline="") as f: review=list(csv.DictReader(f))
    with (out/"paired_transitions.csv").open(encoding="utf-8-sig",newline="") as f: paired=list(csv.DictReader(f))
    assert len(review) == len({r["case_id"] for r in review}) == 45
    assert len(paired) == len({r["case_id"] for r in paired}) == 606
    assert [r["claim_id"] for r in review] == stats["sarol"]["miss45_ids"]
    assert [r["case_id"] for r in review] == [r["case_id"] for r in payload]
    for i,r in enumerate(review):
        full=payload[i]
        assert (r["gold"],r["M0_pred"],r["Mbio_pred"]) == ("NOT_ACCURATE","NOT_ACCURATE","ACCURATE")
        assert full["original_model_input"]["input_sha256"] == r["frozen_input_sha256"]
        assert full["frozen_gold_record"]["label"] == r["gold"]
        assert r["claim_text"] == full["original_model_input"]["user_prompt"].split("\n候选证据：",1)[0].removeprefix("引用论断：")
        assert r["li_reason_codes"] == r["chen_reason_codes"] == r["reason_codes"] == ""
        if r["case_id"] != "sarol:test:51":
            assert r["li_label"] == r["chen_label"] == r["resolved_label"] == ""
    assert sum(r["review20_reused"].lower()=="true" for r in review) == 1
    assert sum(r["gold_evidence_missing"].lower()=="true" for r in review) == 10
    for r in paired:
        if r["is_miss45"].lower()=="true": assert r["case_id"] in {x["case_id"] for x in review}
    old_hashes=json.loads((out/"source_manifest.json").read_text(encoding="utf-8"))
    for v in old_hashes["source_files"].values(): assert sha(Path(v["path"]))==v["sha256"]
    dump(out/"index_audit.json",{"status":"passed_index_and_csv_roundtrip_checks","date":"2026-10-20",
                                  "selected_unique_cases":45,"paired_rows":606,"payload_records":45,
                                  "source_files_unchanged":True,"all_case_ids_and_source_records_align":True,
                                  "copied_previous_label_review":1,"new_label_review_pending":44,"reason_code_review_pending":45,
                                  "gold_reference_spans_in_original_corpus_verified":True,"outside_input_spans_explicitly_marked":True,
                                  "actual_gold_evidence_missing_preserved":10,"model_inference_performed":False})
    readme = """# Sarol 45 条错引漏检全量索引

生成日期：2026-10-20。筛选范围为冻结的 Sarol Test606：gold=NOT_ACCURATE、M0=NOT_ACCURATE、Mbio=ACCURATE。恰好 45 条，未按人工复核结果筛除样本。

## 文件与使用

- `miss45_review.csv`：本周 45 条复核主表。Excel 打开后按列筛选，双方各填自己的标签、证据编号、理由、原因码、日期及预测暴露情况。
- `miss45_payload.jsonl`：45 条完整原始输入、候选证据、M0/Mbio 原始响应及完整记录、冻结 gold 和金证据引用。主表的 payload_line 从 1 起，与此文件逐行对应。
- `paired_transitions.csv`：固定 606 条逐条配对，包含 gold、两模型预测、修复/退化标记及 45 条筛选标记；1 条 M0 INVALID 仍在原分母内。
- `paired_summary.json`：所有核心统计及完整 45 个 ID，含 9 条修复与额外 2 条漏判的 ID。
- `prior_review/review20_final.jsonl`：此前已确认的 20 例只读存档；`review20_overlap.jsonl` 是其中与本 45 条重合的 sarol:test:51，复用其原判断和理由。
- `gold_questions_sidecar.jsonl`：初始空表，后续疑似金标问题另行记录；当前为空不表示 gold 已经全部人工核验无误。
- `source_manifest.json`、`index_audit.json`：源文件路径、哈希、实际源仓库 commit 与核对结果。

同一条只维护主表一行，不为重合案例再建第二份人工表。此前 20 例只有 test:51 与本清单重合；其余 44 条尚待两人逐条复核。该重合条目的本周原因码与暴露记录也仍需补齐，当前 45 条原因码均未自动代填。

## 统计口径

| 统计 | 数量与含义 |
|---|---|
| 修复 / 新增错误 / 净增正确 | 186 / 51 / 135 |
| 修复按 gold 分类 | ACCURATE 177、NOT_ACCURATE 9 |
| 新增错误按 gold 分类 | NOT_ACCURATE 45、IRRELEVANT 6 |
| NOT_ACCURATE 召回 | M0 132/170，Mbio 96/170，少 36 条 |
| 36 的分解 | 45 条新增漏检减 9 条修复 |
| NOT_ACCURATE 被判 ACCURATE | 24/170 增为 71/170，净增 47 |
| 47 的分解 | 原来判对的 45 条，加原来判 IRRELEVANT 的 2 条 |
| SciCiteVal Mscv 对照 | 修复 19、新增错误 9；NOT_ACCURATE 召回 52/89 增为 67/89 |

45、36、47 衡量不同集合，不能混作同一个数。

## 复核填写规则

两模型预测在本表与 payload 中可见，当前按非盲复核管理。每位复核者填写实际是否看过预测。旧 test:51 的历史暴露状态未单独记录，保留 unknown_from_prior_record；不能据文件名推定未暴露。

原因码可多选，用分号分隔：SEM 语义误读、RET 检索遗漏、CTX 输入证据不足、ATT 引用归属、FMT 格式解析、PIPE 实际工程错位或截断、UNK 待核。SEM 子码为否定、方向、数量、条件、对象、过度概括。RET 须指向原检索语料内的证据，PIPE 须附日志。未复核时留空；UNK 也须由实际复核者填写具体待核原因，不能自动填满。

payload 的 gold_reference_spans_diagnostic_only 取自原 gold 引用的源语料句子，句号索引从 0 起。每句标明是否进入原模型候选；标为 false 的额外句子只能用于检索诊断，不能冒称模型已经看到。45 条中 10 条原 gold 的 evidence_missing=true，仍保留其明确分类标签和原记录，不凭缺金证据删除样本。

gold_question_status 初始为 not_reviewed_for_this_week。疑点另写 sidecar，注明原 gold、疑点、双方意见及证据路径，正式 gold 和指标保持原值。本阶段仅生成全量索引，未运行模型、未完成新的 44 条双人判断或 45 条归因。

## 复算

在仓库根目录执行以下命令，并把 review20 路径替换为实际归档文件。使用新输出目录，避免覆盖人工填写内容。Node 依赖使用已配置的 @oai/artifact-tool；生成 CSV 的脚本为 `code/ly/write_route1_miss45_tables_v3.mjs`。

```text
python code/ly/build_route1_miss45_index_v3.py --phase prepare --review20 <20例最终记录.jsonl> --output-dir <新输出目录> --tables-json <中间表.json>
node code/ly/write_route1_miss45_tables_v3.mjs <中间表.json> <QA目录>
python code/ly/build_route1_miss45_index_v3.py --phase finalize --output-dir <新输出目录>
```

源 v2 数据、模型响应与既有 20 例判断均按文件哈希和 (dataset, split, claim_id) 连接；606 条未丢失、45 条无重复，完整原始输出保留在 payload。生成器本身的文件哈希单列，不将未提交脚本伪称已属于源仓库 commit。
"""
    (out/"README.md").write_text(readme,encoding="utf-8")
    # Compact field descriptions supplement the stable machine-readable headers.
    dump(out/"field_dictionary.json",{
        "case_id":"dataset:split:claim_id; join on the full case key",
        "payload_line":"1-based line in miss45_payload.jsonl; never truncate the linked original text",
        "gold":"unchanged label in frozen v2 test.gold.jsonl; not an adjudicated new gold",
        "gold_evidence_missing":"original metadata; does not mean the classification label is absent",
        "gold_reference_not_in_input_count":"reference occurrences; not a unique-case count or automatic RET diagnosis",
        "review_mode":"non_blind_prediction_visible; reviewer-specific actual exposure fields remain to be filled",
        "reason_codes":{"allowed":["SEM","RET","CTX","ATT","FMT","PIPE","UNK"],"separator":";","initial":"blank pending actual review"},
        "sem_subtypes":{"allowed":["否定","方向","数量","条件","对象","过度概括"],"separator":";"},
        "review20_reused":"only sarol:test:51; labels/reasons retained from prior confirmed record",
        "resolved_label":"prior accepted label if reused; new-case judgments left blank",
        "gold_question_status":"not_reviewed_for_this_week initially; concerns in a separate sidecar",
        "boolean_encoding":"CSV true/false; JSON/JSONL native booleans"})
    manifest={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name!="file_hashes.json"}
    dump(out/"file_hashes.json",manifest)
    if args.bundle:
        args.bundle.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(args.bundle,"w",zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob("*")):
                if p.is_file():z.write(p,"error_analysis/"+p.relative_to(out).as_posix())
            for name in ("build_route1_miss45_index_v3.py","write_route1_miss45_tables_v3.mjs"):
                p=REPO/"code/ly"/name
                z.write(p,"code/ly/"+name)
        with zipfile.ZipFile(args.bundle) as z:
            assert z.testzip() is None
            for p in out.rglob("*"):
                if p.is_file():assert z.read("error_analysis/"+p.relative_to(out).as_posix())==p.read_bytes()
    print(js({"phase":"finalize","status":"passed","review_rows":45,"paired_rows":606,"new_reviews_pending":44,
              "reason_codes_pending":45,"output_dir":str(out),"bundle":str(args.bundle) if args.bundle else None,
              "bundle_sha256":sha(args.bundle) if args.bundle else None}))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--phase",choices=("prepare","finalize"),required=True)
    p.add_argument("--repo-root",type=Path,default=REPO)
    p.add_argument("--output-dir",type=Path,default=REPO/"results/route1_qwen38_v3/2026-10-25/error_analysis")
    p.add_argument("--review20",type=Path)
    p.add_argument("--tables-json",type=Path,default=REPO.parent/"tmp/route1_miss45_20261020/tables.json")
    p.add_argument("--bundle",type=Path)
    a=p.parse_args()
    a.repo_root=a.repo_root.resolve();a.output_dir=a.output_dir.resolve();a.tables_json=a.tables_json.resolve()
    if a.review20 is None:
        archived=a.output_dir/"prior_review/review20_final.jsonl"
        a.review20=archived if archived.exists() else REPO.parent/"发给师兄_本周汇报_2026-10-19/05_Test配对与案例复核/20案例共同裁决完成_20261019/20案例复核最终记录.jsonl"
    if a.phase=="prepare":prepare(a)
    else:finalize(a)

if __name__=="__main__":main()
