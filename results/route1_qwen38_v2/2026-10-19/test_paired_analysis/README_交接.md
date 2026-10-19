# 路线一 Test 配对分析交接（2026-10-19）

## 当前状态

- 六个冻结分类 Test 的逐条配对统计已完成，模型与输入未重跑。
- 每个 Test 选出 10 条，共 20 条代表案例，保存完整输入、候选证据、冻结 gold 和三模型原始输出。
- Codex 对 20 条只作来源初筛；李云、陈明进的独立判断及共同裁决仍待填写。表格中的“待填写”不是签核结果。
- 发现疑似金标/给定段落边界问题时仅标记待裁决；没有修改 gold 或六组正式指标。

## 文件

| 文件 | 用途 |
|---|---|
| `配对变化与20案例交接_20261019.md` | 可阅读的指标、配对变化和逐案例初筛说明 |
| `路线一Test配对变化与20案例_20261019.xlsx` | 三张表：结论、863 条逐条配对、20 条待复核案例 |
| `paired_summary.json` | 四组 M0 对 adapter 配对计数、类别分层、转移矩阵与源文件 SHA-256 |
| `paired_rows.jsonl` | SciCiteVal 257 条和 Sarol 606 条逐条三模型标签与对错 |
| `case_review_packet.jsonl` | 20 条完整原始输入、证据、响应及留空的双人复核字段 |
| `盲复核表_李云_20261019.jsonl`、`盲复核表_陈明进_20261019.jsonl` | 两份各 20 条独立复核用原始输入；不含 gold、模型输出和 Codex 初筛意见 |
| `盲复核说明_20261019.md` | 仅含三类标签判断口径和填写方法，可与盲复核表单独发送 |
| `analyze_route1_test_pairs.py`、`build_case_packet.py`、`build_blind_forms.py`、`build_report.py`、`case_triage_notes.json` | 复算与重建数据交付文件 |

## 复算来源

- 仓库根目录：`academic-misconduct`，冻结数据在 `results/route1_qwen38_v2/2026-10-15/{sciciteval,sarol}/test.{inputs,gold}.jsonl`。
- 原始运行：`route1_qwen38_v2_test_20261018_refreeze5120_run02`，六组 `*_test_predictions.jsonl` 和 `*_test_metrics.json`。
- 冻结推理长度 5120、最多新生成 512 token、reasoning off、无重试。Sarol M0 的 1 条 INVALID 按错误保留。
- 每个 Test 分别按 `(dataset, claim_id)` 与 gold 连接。输入、gold 和预测 SHA-256 位于 `paired_summary.json`。

复算命令（在本地资料目录下，将路径替换为实际仓库与运行结果路径）：

```text
python analyze_route1_test_pairs.py --repo-root <repo> --run-root <run02> --out-dir <本目录>
python build_case_packet.py --repo-root <repo> --run-root <run02> --paired-rows paired_rows.jsonl --triage-notes case_triage_notes.json --out-dir <本目录>
python build_blind_forms.py --cases case_review_packet.jsonl --out-dir <本目录>
python build_report.py --summary paired_summary.json --cases case_review_packet.jsonl --output 配对变化与20案例交接_20261019.md
```

## 待完成的人工动作

1. 李云与陈明进**先各自使用对应的盲复核表**，看完整候选证据并填写标签、证据依据、日期和姓名。盲审提交前不打开含 gold/预测的完整案例包或表格。
2. 对不一致条目保留两个原判断，再打开完整交接表，记录共同裁决及原因。优先复核 SciCiteVal `test:608`、`test:124`、`test:34` 和 Sarol `test:1`。
3. 将错误原因分为检索遗漏、输入截断、引用对象归属、标签边界、语义、格式等，并与正式分类指标分开报告。

本包只完成分类 Test 的配对分析和案例交接，**不是**两人独立复核完成证明，也不是双 PDF 原型验收材料。
