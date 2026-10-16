# 两篇 PDF 引用闭环演示：SciCiteVal → SciFact

这是路线一的独立 PDF 流程样例，**不属于**冻结的 SciCiteVal/Sarol Train、Dev、Test，也不计入六个 Dev 单元。当前状态是 `prepared_no_model_run`：已核对两篇 PDF、引用点、参考文献条目和被引证据，模型尚未对该样例推理。

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

下一步用正式 Mscv adapter 对 `demo.inputs.jsonl` 做一次独立推理，保留原始 JSON、证据编号、理由与输出文件哈希。即使复用现有评测 CLI 的 `--split dev` 参数，其输出也必须保存在独立 `pdf_demo` 目录，不计入正式 Dev54 或 checkpoint 选择。
