# 两篇 PDF 引用闭环演示：SciCiteVal → SciFact

这是路线一的独立 PDF 流程样例，**不属于**冻结的 SciCiteVal/Sarol Train、Dev、Test，也不计入六个 Dev 单元。两篇 PDF、引用点、参考文献条目和被引证据已核对；正式 Mscv adapter 已对该样例运行一次标签判定。当前状态为 `model_label_run_completed_schema_partial`：模型只输出标签，尚未生成证据编号和理由。

## 来源与定位

| 角色 | 本地文件 | SHA-256 | 定位 |
|---|---|---|---|
| 施引论文 | `01_SciCiteVal_LREC2026.pdf` | `db7451e45296f066d3fa8c5b35d2ae2d2620b7ebeba85fbae2eb583d9f1246cf` | PDF 第 2 页，`Wadden et al. (2020)`；参考文献第 9 页 |
| 被引论文 | `02_SciFact_Wadden_2020.pdf` | `e51a1fab569f2dcb00f7806fe95094e25a34c027140709725d3d05b7a0af9ac7` | PDF 第 1 页摘要 |

施引论文的参考文献条目与被引 PDF 的标题、作者对应。引用论断说 SciFact 有约 1.4K 条专家撰写的科学论断，配有论文摘要中的证据、SUPPORTS/REFUTES 标签和理由。被引论文摘要前两句直接支持这些内容。人工参考标签暂记为 `ACCURATE`，供流程演示；它不是冻结数据集的 gold。

现有 PDF 句子索引及 BM25 检索将被引摘要 `P001:B010:S001` 排第 1 位；同时取其上一句 `P001:B010:S000`，使 SUPPORTS/REFUTES 说明完整进入单个候选证据 `D01:S01`。`citation_loop.json` 保存页码、引用标记矩形、参考文献定位、证据句号、block bbox、原始 PDF 哈希和输入哈希。证据送入模型前仅修复 PDF 换行断词和连字，未增补外部内容。当前证据 bbox 的粒度仍是文本块；不能当作逐句精确矩形。

## 重建

两篇原始 PDF 在本地仓库同级的 `member2_papers/`，没有提交到 Git。仓库根目录执行：

```bash
python -X utf8 code/ly/build_route1_pdf_loop_demo_v1.py \
  --citing-pdf ../member2_papers/01_SciCiteVal_LREC2026.pdf \
  --cited-pdf ../member2_papers/02_SciFact_Wadden_2020.pdf
```

脚本沿用冻结 SciCiteVal v2 的 system prompt 与 `D01:S01` 格式，生成 `demo.inputs.jsonl`、`demo.reference_gold.jsonl` 和 `citation_loop.json`。模型调用时只传前者的 `system_prompt` 和 `user_prompt`；外部 ID、参考标签和 PDF 定位元数据不进入提示词。

## 模型运行与限制

2026-10-16 在 A100 上用官方 HF 底座和正式 Mscv `final_adapter` 独立运行该单条输入，`enable_thinking=False`、`max_length=4096`、`max_new_tokens=512`、无重试。评测 CLI 仅因参数约束使用 `--split dev`，实际输出写入独立 `route1_qwen38_v2_pdf_demo_20261016/Mscv/`，**不属于**正式 Dev54，也不参与 checkpoint 选择。原始逐条预测已按 A100 文件字节复现到 [Mscv_pdf_demo_dev_predictions.jsonl](Mscv_pdf_demo_dev_predictions.jsonl)，其 SHA-256 与服务器核对一致：`1f42160a1dcab37749b046948f84241c2b962f4164be79c12abd70703ccb9fcb`。服务器指标文件 SHA-256 为 `55b8352b00b4c1e85c7770a33e627978ca7cf5d00ba680117522c609e2896ec4`，文件仍留在 A100。

模型输出原文是 `{"label": "ACCURATE"}`；标签与人工演示参考标签一致，评测器按标签解析记为 1/1、`invalid_reason=null`。这不是正式评测分数。**原始输出没有 `evidence_ids`、`reason` 或 `confidence`**：这些字段虽写在冻结提示词中，但 Mscv 训练目标只监督标签 JSON，现有评测器也只校验标签。因此不能把人工参考理由或输入中的 `D01:S01` 说成模型生成的解释。`citation_loop.json` 的 `prepared_no_model_run` 是输入构建时的静态状态；本节记录后续独立模型运行。

下一步需要由路线一负责人确认解释字段的模型输出方案及评测规则，再对真实两篇 PDF 完成可验收的“证据编号与理由”闭环。保持冻结 v2 Train/Dev/Test 和本次原始预测不变。
