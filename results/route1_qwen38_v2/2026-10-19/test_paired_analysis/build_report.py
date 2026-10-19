"""Render the checked paired comparison and the 20-case handoff note."""

import argparse
import json
from pathlib import Path


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = [
        "# 路线一 v2 六个 Test 配对变化与 20 案例复核交接",
        "",
        "日期：2026-10-19。数据范围：冻结 Test；SciCiteVal 257 条、Sarol 606 条。",
        "状态：**配对统计已完成；20 条案例的来源初筛已完成；两人独立证据复核和裁决尚未完成。**",
        "此分析只使用本地保存的 run02 原始预测，不运行模型、不调整 checkpoint、gold 或 Test 配置。",
        "",
        "## 六个分类 Test 指标（按冻结 gold）",
        "",
        "| 数据集 | 模型 | 正确/总数 | Accuracy | Macro-F1 | 无效输出 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for dataset, meta in summary["datasets"].items():
        for model in ("M0", "Mbio", "Mscv"):
            metric = meta["model_metrics"][model]
            lines.append(f"| {dataset} | {model} | {metric['correct']}/{meta['records']} | {pct(metric['accuracy'])} | {metric['macro_f1']:.6f} | {metric['invalid_count']} |")
    lines += [
        "",
        "## 各 adapter 与 M0 的同一条目配对结果",
        "",
        "“修复”表示 M0 错、adapter 对；“新增错误”表示 M0 对、adapter 错，均仅针对冻结 gold。",
        "",
        "| Test | adapter | 双方正确 | 修复 | 新增错误 | 双方错误 | 净正确数 | Accuracy 差（百分点） | Macro-F1 差 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for dataset, meta in summary["datasets"].items():
        for adapter in ("Mbio", "Mscv"):
            item = meta["comparisons"][adapter]
            count = item["outcome_counts"]
            lines.append(
                f"| {dataset} | {adapter} | {count.get('both_correct', 0)} | {count.get('repaired_error', 0)} | "
                f"{count.get('new_error', 0)} | {count.get('both_wrong', 0)} | {item['net_correct_change']:+d} | "
                f"{item['accuracy']['delta_percentage_points']:+.2f} | {item['macro_f1']['delta']:+.6f} |"
            )
    lines += [
        "",
        "### 变化的具体方向",
        "",
        "- **SciCiteVal / Mscv（本域）：**修复 19、新错 9，净增 10 条正确；修复主要来自金标 NOT_ACCURATE（17 条），新错包括 7 条金标 ACCURATE 被改错。",
        "- **SciCiteVal / Mbio（跨域）：**修复 5、新错 22，净减 17 条正确；22 条新错均为金标 NOT_ACCURATE 被判成 ACCURATE。",
        "- **Sarol / Mbio（本域）：**修复 186、新错 51，净增 135 条正确；其中 177 条修复为金标 ACCURATE，45 条金标 NOT_ACCURATE 新错被判为 ACCURATE，另有 6 条金标 IRRELEVANT 新错。",
        "- **Sarol / Mscv（跨域）：**修复 58、新错 14，净增 44 条正确；修复中 52 条金标 ACCURATE，新错覆盖三个标签。",
        "",
        "按配对结果，两个 adapter 在本域均提高分类 Accuracy 和 Macro-F1；Mscv 在 Sarol 也提高，Mbio 在 SciCiteVal 下降。"
        "这四个比较只描述当前冻结数据及模型，不用 Test 重新挑 checkpoint。",
        "SciCiteVal 输入给定被引段落；Sarol 输入为检索到的十句，两套 Test 的绝对分数不能直接当作领域难度比较。",
        "SciCiteVal 的 79 条 IRRELEVANT Test 是受限构造来源，不能据此推断一般无关引用识别能力。",
        "",
        "## 20 条代表案例：来源初筛，待双人复核",
        "",
        "选取每个 Test 10 条，覆盖三类 gold、改善、退化、双方错误和 Sarol M0 的唯一无效输出。",
        "这是一组刻意挑选的诊断样本，**不能**据此估计总体错误率。",
        "完整输入、候选证据、三模型原始响应及 frozen gold 均保存在 `case_review_packet.jsonl`。",
        "下表的观察是 Codex 对提供文本的辅助初筛；不是李云或陈明进的独立签核，也不改冻结分数。",
        "为避免预测与 gold 影响独立判断，两位复核者应先分别使用 `盲复核表_李云_20261019.jsonl`、`盲复核表_陈明进_20261019.jsonl`，不要先看下表或完整案例包。",
        "",
        "| 案例 | gold | M0 / Mbio / Mscv | 来源初筛焦点 | 需核对的依据 |",
        "|---|---|---|---|---|",
    ]
    for row in cases:
        triage = row["codex_source_triage"]
        mark = " ⚠待裁决" if triage["requires_gold_adjudication"] else ""
        note = triage["source_check_note"].replace("|", "\\|")
        preds = " / ".join(row["predictions"][model] for model in ("M0", "Mbio", "Mscv"))
        lines.append(f"| {row['case_id']} | {row['gold']} | {preds} | {triage['review_focus']}{mark} | {note} |")
    lines += [
        "",
        "### 特别待裁决项",
        "",
        "- SciCiteVal `test:608` 的给定段落与论断表面上直接相符，但 gold 为 IRRELEVANT；`test:124`、`test:34` 的 gold 支持范围也需核对。",
        "- Sarol `test:1` 的部分候选句似乎支持其菌群依赖机制，但 gold 为 NOT_ACCURATE；需要读完整上下文，不能据初筛改标。",
        "- 在这 20 条中，Sarol 若干条没有命中已标注 gold 的精确 `(doc_id, sentence_id)`。这只说明该精确句未进入十句候选；其他候选句仍可能提供替代支持，不能自动判定为检索失败。",
        "",
        "## 复核与验收边界",
        "",
        "1. 李云和陈明进各自使用对应的盲复核表，独立填写标签、证据编号/原文和理由，并记录姓名与日期。两份表均不含 gold、模型预测或 Codex 初筛意见。",
        "2. 两人提交各自原始记录后，再打开本交接表与完整案例包，讨论不一致条目。把争议分成检索遗漏、输入截断、引用对象归属、标签边界、语义或格式问题；保留模型原输出、冻结 gold 和裁决记录。",
        "3. 20 条人工复核完成前，本文件只能作为**配对统计和案例交接稿**；真实双 PDF 流程验收另行进行。",
        "",
        "## 可复算性",
        "",
        "- 连接键：`(dataset, claim_id)`，每个 Test 内预测顺序与 gold 顺序一致；跨数据集不能只按 claim_id 连接。",
        "- `paired_summary.json` 保存四组配对计数、按 gold 分层计数、预测标签转移矩阵和输入/输出文件 SHA-256；`paired_rows.jsonl` 保存 863 条逐条对照。",
        "- 原始预测文件 SHA-256 与各自指标文件记录一致；脚本独立复算六组 Accuracy、Macro-F1 与无效输出数。Sarol M0 唯一无效输出仍按错误计入。",
        "- 冻结 Test 推理长度统一为 5120，最多新生成 512 token；本工作没有修改模型或重新推理。",
        "",
    ]
    args.output.write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
