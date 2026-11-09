"""Compare archived Mbio predictions against unchanged frozen Test gold.

No model is loaded. This exports observations for source review; it never
relabels a record, selects a checkpoint, or rewrites an original run.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path


LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")
SCRIPT_DIR = Path(__file__).resolve().parent


def locate_repo() -> Path:
    for parent in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        for candidate in (parent, parent / "_route1_test_pair_publish_20261019"):
            if (candidate / "results/route1_qwen38_v2/2026-10-15").is_dir():
                return candidate
    raise FileNotFoundError("Frozen Route 1 data repository was not found")


REPO = locate_repo()
BASE = REPO / "results/route1_qwen38_v3/2026-10-25/mbio_reproduction"
GOLD_ROOT = REPO / "results/route1_qwen38_v2/2026-10-15"
OLD_ROOT = REPO / "results/route1_qwen38_v2/2026-10-19/test_refreeze5120_run02/test"
DETAIL = SCRIPT_DIR / "新旧Mbio逐样本变化_20261103.jsonl"
REPORT = SCRIPT_DIR / "错引漏检变化分析_20261103.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return Path(os.path.relpath(path, REPO)).as_posix()


def load_rows(path: Path) -> tuple[dict[str, dict], dict[str, int]]:
    rows, lines = {}, {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        cid = str(row["claim_id"])
        if cid in rows:
            raise ValueError(f"Duplicate claim_id={cid} in {path}")
        rows[cid], lines[cid] = row, lineno
    return rows, lines


def coverage(rec: dict, gold: dict, dataset: str) -> dict:
    if dataset != "sarol":
        return {"status": "NO_SENTENCE_ANNOTATIONS_IN_THIS_GOLD_SCHEMA"}
    annotated = gold.get("gold_evidence") or {}
    pairs = {(str(doc), sid) for doc, xs in annotated.items()
             for x in xs for sid in x.get("sentences", [])}
    evidence = rec.get("candidate_evidence", [])
    hits = [e["evidence_id"] for e in evidence
            if (str(e.get("doc_id")), e.get("sentence_id")) in pairs]
    docs = sorted({str(e["doc_id"]) for e in evidence
                   if str(e.get("doc_id")) in annotated})
    status = ("NO_ANNOTATED_SENTENCE_AVAILABLE" if not pairs else
              "AT_LEAST_ONE_ANNOTATED_SENTENCE_VISIBLE" if hits else
              "ANNOTATED_DOCUMENT_VISIBLE_SENTENCE_NOT_SELECTED" if docs else
              "ANNOTATED_DOCUMENT_NOT_IN_CANDIDATES")
    return {"status": status, "matched_evidence_ids": hits,
            "annotated_doc_ids": sorted(annotated), "visible_annotated_doc_ids": docs,
            "frozen_evidence_missing": gold.get("evidence_missing")}


def write_result(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise FileExistsError(f"Existing different result preserved: {path}")
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    exports, summaries, sources = [], {}, {}
    for dataset, expected_n in (("sarol", 606), ("sciciteval", 257)):
        op = OLD_ROOT / dataset / "Mbio/Mbio_test_predictions.jsonl"
        np = BASE / "corrected_20261031/test" / dataset / "Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_predictions.jsonl"
        ip = GOLD_ROOT / dataset / "test.inputs.jsonl"
        gp = GOLD_ROOT / dataset / "test.gold.jsonl"
        om = op.with_name("Mbio_test_metrics.json")
        nm = np.with_name("Mbio_corrected_ckpt134_test_metrics.json")
        old, ol = load_rows(op)
        new, nl = load_rows(np)
        inputs, il = load_rows(ip)
        gold, gl = load_rows(gp)
        assert len(gold) == expected_n
        assert set(old) == set(new) == set(inputs) == set(gold)
        for name, path in (("old_predictions", op), ("new_predictions", np),
                           ("inputs", ip), ("gold", gp), ("old_metrics", om), ("new_metrics", nm)):
            sources[f"{dataset}.{name}"] = {"path": rel(path), "sha256": sha(path)}
        for mp, pp in ((om, op), (nm, np)):
            m = json.loads(mp.read_text(encoding="utf-8"))
            assert m["inputs_sha256"] == sha(ip)
            assert m["gold_sha256"] == sha(gp)
            assert m["prediction_sha256"] == sha(pp)
            assert m["max_length"] == 5120 and m["max_new_tokens"] == 512
            assert m["enable_thinking"] is False
        transitions, outcomes, by_gold, cov = Counter(), Counter(), {}, Counter()
        for cid, g in gold.items():
            a, z, rec = old[cid], new[cid], inputs[cid]
            target, before, after = g["label"], a["pred"], z["pred"]
            assert a["gold"] == z["gold"] == target
            assert target in LABELS and before in LABELS and after in LABELS
            assert a.get("retry_count", 0) == z.get("retry_count", 0) == 0
            transitions[(target, before, after)] += 1
            outcome = ("C" if before == target else "W") + ("C" if after == target else "W")
            outcomes[outcome] += 1
            row_cov = coverage(rec, g, dataset)
            missed = target == "NOT_ACCURATE" and before == target and after != target
            repaired = target == "NOT_ACCURATE" and before != target and after == target
            if missed:
                cov[row_cov["status"]] += 1
            prompt = rec["user_prompt"]
            claim = prompt.split("\n候选证据：", 1)[0].split("\n被引内容：", 1)[0]
            claim = claim.removeprefix("引用论断：").removeprefix("施引上下文：")
            exported = {
                "case_id": f"{dataset}:test:{cid}", "dataset": dataset, "split": "test",
                "claim_id": cid, "frozen_gold": target,
                "old_checkpoint": "historical_checkpoint-100",
                "corrected_checkpoint": "corrected_checkpoint-134",
                "old_prediction": before, "corrected_prediction": after,
                "correctness_transition": outcome, "prediction_changed": before != after,
                "new_NOT_ACCURATE_miss": missed, "repaired_NOT_ACCURATE_miss": repaired,
                "claim_text": claim, "candidate_count": len(rec.get("candidate_evidence", [])),
                "candidate_annotation_diagnostic": row_cov,
                "source_locations": {
                    "old_predictions": {"path": rel(op), "line": ol[cid]},
                    "corrected_predictions": {"path": rel(np), "line": nl[cid]},
                    "frozen_inputs": {"path": rel(ip), "line": il[cid]},
                    "frozen_gold": {"path": rel(gp), "line": gl[cid]},
                },
                "human_scope_review": None, "human_label_review": None,
                "causal_attribution": None,
            }
            if missed or repaired:
                exported["frozen_candidate_evidence_for_review"] = rec.get("candidate_evidence", [])
                exported["frozen_gold_record_for_review"] = g
            exports.append(exported)
        for target in LABELS:
            sub = {(a, z): n for (g, a, z), n in transitions.items() if g == target}
            support = sum(sub.values())
            before = sum(n for (a, _), n in sub.items() if a == target)
            after = sum(n for (_, z), n in sub.items() if z == target)
            repairs = sum(n for (a, z), n in sub.items() if a != target and z == target)
            losses = sum(n for (a, z), n in sub.items() if a == target and z != target)
            assert after == before + repairs - losses
            by_gold[target] = dict(support=support, old_correct=before, new_correct=after,
                                   repaired=repairs, new_errors=losses)
        for mp, ck in ((om, "old_correct"), (nm, "new_correct")):
            m = json.loads(mp.read_text(encoding="utf-8"))
            assert m["total"] == expected_n and m["correct"] == sum(x[ck] for x in by_gold.values())
            for label in LABELS:
                assert m["per_class"][label]["tp"] == by_gold[label][ck]
        summaries[dataset] = {"count": expected_n, "correctness": dict(outcomes),
                              "by_gold": by_gold, "new_miss_coverage": dict(cov),
                              "old_prediction_counts": dict(Counter(x["pred"] for x in old.values())),
                              "new_prediction_counts": dict(Counter(x["pred"] for x in new.values()))}
    assert len(exports) == 863 and len({x["case_id"] for x in exports}) == 863
    missed = [x for x in exports if x["new_NOT_ACCURATE_miss"]]
    assert len(missed) == 28
    assert summaries["sarol"]["correctness"] == {"WW": 140, "CC": 407, "WC": 32, "CW": 27}
    assert summaries["sciciteval"]["correctness"] == {"CC": 192, "WW": 61, "CW": 4}
    detail_text = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in exports)
    cov_names = {
        "NO_ANNOTATED_SENTENCE_AVAILABLE": "冻结gold无可用证据句标注",
        "AT_LEAST_ONE_ANNOTATED_SENTENCE_VISIBLE": "至少一条标注证据句在候选中",
        "ANNOTATED_DOCUMENT_VISIBLE_SENTENCE_NOT_SELECTED": "标注文档可见，标注句未选入",
        "ANNOTATED_DOCUMENT_NOT_IN_CANDIDATES": "标注文档未进入候选",
        "NO_SENTENCE_ANNOTATIONS_IN_THIS_GOLD_SCHEMA": "该gold格式不含句级证据标注",
    }
    md = ["# 新旧Mbio错引漏检变化分析", "", "日期：2026-11-03。阶段：冻结Test逐样本观察与复核准备。", "",
          "Sarol错引判对数由96降至73：72条持续判对，24条原本判对而本轮漏检，另修复1条旧漏检，即96 − 24 + 1 = 73。新增24条漏检中18条转为ACCURATE、6条转为IRRELEVANT。Sarol总体修复32条、产生27条新增错误，净多判对5条。", "",
          "SciCiteVal有4条新增错误，全部为NOT_ACCURATE转为ACCURATE；没有修复旧错误。两域合计28条新增错引漏检，均已按稳定case_id附原论断和冻结证据，留待陈明进复核。", "",
          "## 数据来源与统计边界", "",
          "比较历史Mbio checkpoint-100与纠正Mbio checkpoint-134。606条Sarol和257条SciCiteVal按各自claim_id对齐，跨域使用dataset、split、claim_id联合键。两次评估的输入/gold哈希一致，均为5120/512、关闭reasoning，首次响应且无重试。选点仍依据Sarol Dev；此处Test分析仅作错误诊断。", "",
          "CC表示两次均判对，WC为修复，CW为新增错误，WW为两次均判错。判对/判错均相对于冻结gold；候选标注匹配只说明可见性。所有人工复核及因果归属字段为空，未修改标签或成绩。", "",
          "## 按冻结标签的变化", "",
          "| 数据集 | 冻结gold | 条数 | 旧判对 | 新判对 | 修复 | 新增错误 | 净变化 |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    for ds, stats in summaries.items():
        for label in LABELS:
            d = stats["by_gold"][label]
            md.append(f"| {ds} | {label} | {d['support']} | {d['old_correct']} | {d['new_correct']} | {d['repaired']} | {d['new_errors']} | {d['new_correct']-d['old_correct']:+d} |")
    md += ["", "Sarol的改善来自ACCURATE净增21条及IRRELEVANT净增7条，抵消NOT_ACCURATE净减23条，因此总准确率改善可以与错引召回下降同时发生。", "",
           "## 预测分布与候选证据诊断", "",
           "Sarol输出NOT_ACCURATE由186条降到133条，ACCURATE由388条升到426条，IRRELEVANT由32条升到47条。这支持‘输出分布向其余两类移动’这一观察；两次比较同时涉及不同训练运行和checkpoint，不能单凭这些统计把变化全部归因于归一化修复。", "",
           "24条Sarol新增错引漏检的证据可见性如下：", "",
           "| 技术诊断 | 条数 | 后续复核内容 |", "|---|---:|---|"]
    questions = {
        "NO_ANNOTATED_SENTENCE_AVAILABLE": "冻结gold没有可用句级标注，先核对标签出处和引用范围；不据此判定标签错。",
        "AT_LEAST_ONE_ANNOTATED_SENTENCE_VISIBLE": "候选已有标注句，逐项核对否定、对象、研究条件和完整主张。",
        "ANNOTATED_DOCUMENT_VISIBLE_SENTENCE_NOT_SELECTED": "核对未选入的标注句能否解释差异；不以文档出现替代句子覆盖。",
        "ANNOTATED_DOCUMENT_NOT_IN_CANDIDATES": "核对候选构造与引用文献归属；未命中不等于源文无证据。",
    }
    for key in questions:
        md.append(f"| {cov_names[key]} | {summaries['sarol']['new_miss_coverage'].get(key,0)} | {questions[key]} |")
    md += ["", "以上类别是冻结记录和ID匹配的技术分组，不是最终错误归因；句子命中也不保证其支持全部主张。SciCiteVal的gold没有句级证据标注，不并入这项覆盖统计。", "",
           "## 代表案例及复核问题", "",
           "以下五例展示原冻结输入中的核对点，正式语义复核仍待陈明进意见：", "",
           "| case_id | 预测变化 | 冻结输入中的可核对点 |", "|---|---|---|",
           "| sarol:test:385 | NOT_ACCURATE → IRRELEVANT | D01:S01、D04:S01含远程精神卫生服务证据；需核对它们与论断中early psychosis、inpatient及hybrid限定的关系。 |",
           "| sarol:test:426 | NOT_ACCURATE → ACCURATE | D07:S01为‘Combination therapy and thiopurines may be associated…’；需核对其是否支持论断对corticosteroids和immunomodulators的完整归属。 |",
           "| sarol:test:604 | NOT_ACCURATE → ACCURATE | 论断称fruit and vegetable intake无变化；D01:S01写vegetable无变化、fruit intake increased (P = 0.055)。需核对字面方向与统计表述，不能只按主题相似判断。 |",
           "| sciciteval:test:67 | NOT_ACCURATE → ACCURATE | 论断写doesn't keep…from converging；冻结段落写effectively keeps both…from converging。需核对否定及更新机制范围。 |",
           "| sciciteval:test:95 | NOT_ACCURATE → ACCURATE | 论断写based on BERT embeddings；冻结段落写based on TransE embedding。需核对嵌入方法替换这一关键细节。 |", "",
           "## 28条新增错引漏检全量索引", "",
           "逐样本明细包含863条比较。对新增漏检和修复的错引另附冻结候选与gold原记录，个人及共同判断字段均未代填。", "",
           f"[逐样本记录]({DETAIL.name})", "",
           "| case_id | 新预测 | 候选证据技术状态 |", "|---|---|---|"]
    for row in missed:
        md.append(f"| {row['case_id']} | {row['corrected_prediction']} | {cov_names[row['candidate_annotation_diagnostic']['status']]} |")
    repaired = [x["case_id"] for x in exports if x["repaired_NOT_ACCURATE_miss"]]
    md += ["", "修复的旧错引漏检：" + "、".join(repaired) + "。", "",
           "## 后续安排", "",
           "李云已完成逐样本对齐、修复/新增错误统计和冻结证据整理。陈明进下一步集中复核28条新增漏检中的范围、版本和关键条件，优先从上列五例入手，同时检查覆盖分组。标签出处无法核清的继续待核，原gold继续保留用于基准统计。", "",
           "待上述复核回收后再形成有证据的错误类型结论。可在Dev验证的实验方向包括候选证据覆盖诊断、否定与方法/数值等关键条件的训练样本复核，以及类别判断偏向检查；这些是待验证建议，当前没有批准新训练，也没有依据Test重新选checkpoint。", "",
           "## 来源哈希", "",
           "| 来源 | 仓库相对路径 | SHA256 |", "|---|---|---|"]
    for name, src in sources.items():
        md.append(f"| {name} | {src['path']} | {src['sha256']} |")
    detail_hash = hashlib.sha256(detail_text.encode("utf-8")).hexdigest()
    md += ["", f"逐样本明细SHA256：`{detail_hash}`。", "",
           "核验范围：863个联合ID唯一且与冻结输入/gold一致；原预测和指标文件哈希相符；重算分类TP与既有指标一致；按类别的修复减新增错误等于判对数变化。没有模型加载或新推理。", ""]
    write_result(DETAIL, detail_text)
    write_result(REPORT, "\n".join(md))
    print(json.dumps({"status": "PAIRED_TEST_DIAGNOSTIC_EXPORTED_HUMAN_REVIEW_PENDING",
                      "summaries": summaries, "new_misses": len(missed),
                      "detail": rel(DETAIL), "detail_sha256": sha(DETAIL),
                      "report": rel(REPORT), "report_sha256": sha(REPORT),
                      "new_human_labels": 0, "model_loaded": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
