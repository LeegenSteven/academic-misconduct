# SciCiteVal 五组冲突：已定位证据与最小人工核查单

10 条记录不需要重新搜索。原始文本、完整 evidence、QASA 注释字段和核查问题已放在同名 CSV/JSON。row_id 为 experiment_dataset 的零起始数据记录号，不含表头；原文件不做修改。

可确认两类构造问题：前两组正负均导出为扭曲文本；后三组原注释中 Composition 与 Twisted_composition 相同，未形成预期文本改动。这个诊断足以继续隔离，不等同于已获最终人工标签。

| row_id | QASA / paper | 已证实的问题 | 只需补核什么 |
|---|---|---|---|
| 358, 359 | 284 / paper_127 | 正负导出均取扭曲版本 | 核对正样本应使用的最终修订文本；确认 whether original Composition 已经被人工改写为 citation，或应恢复其他版本。禁止仅把当前 Correct 标签改为 Incorrect 后当成冲突已修复。 |
| 528, 529 | 941 / paper_43 | 正负导出均取扭曲版本 | 核对正样本最终文本、pre-trained/pre-skilled 实际 intended edit，以及原 Composition 关于 fine-tuning 的表述是否与 evidence 一致。不能仅按字段名自动认定 Composition 为正确。 |
| 556, 557 | 1083 / paper_55 | 原标注中的数值扭曲未形成文本差异 | 请提供 intended 错误数值与实际扭曲后的原始文本/版本；同时澄清 sample length 指输入26帧覆盖时长还是10ms帧移。缺少 intended edit，无法可靠重建负样本。 |
| 562, 563 | 1102 / paper_56 | 扭曲理由存在，扭曲文本未更新 | 请核实 intended negative 的已审定完整文本及其标签；不要直接按替换提示批量制造负样本。确认缩写 ARSG/ASRG 是否另有排版问题。 |
| 590, 591 | 1299 / paper_77 | 扭曲理由存在，扭曲文本未更新 | 请提供最终扭曲文本及原标注记录；核实这组是否因未执行术语替换而导出重复，并复核原 Composition 的 best choice 等表述是否超出 evidence。 |

现有 Qasa_annotated.tsv 哈希为 `fd1e95b14dcc3487a86672e2a00179d7c138a6a50af8c87b7000d9a29a3fae63`，与冻结来源一致。请每组只填写一次 reviewer、review_decision、verified_positive_context、verified_negative_context、supporting_source_or_commit、review_notes；证据不足可填写“维持隔离”。不得按 Twist_reason 机械替换生成新金标准，也不得把修复回填当前 frozen v1。
