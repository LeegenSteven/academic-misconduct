# 师兄裁决执行记录（2026-10-03）

## 回传结论

本记录依据陈明进 2026-10-03 的文字回复，将明确裁决写入派生裁决版；原始回传表、双方个人标注和规范化预合并表均保留不改。

## demo30

- 8 条全部按师兄意见纳入替换集。
- `replacement_04`：纳入；最终标签 `NOT_ACCURATE`。
- `replacement_06`：最终标签 `NOT_ACCURATE`，理由为证据支持急性肝功能失代偿方向，但未充分支持 claim 所称 12%—50% 数值范围。
- 其余 6 条双方标签一致并完成裁决。最终分布：`ACCURATE` 6 条、`NOT_ACCURATE` 2 条。

## seed=42 SciFact

已对双方均有三分类的 17 条写入 `project_label`、`adjudicated_*`：

- `train-78`：`ACCURATE`
- `train-788`：`NOT_ACCURATE`，被引证据未直接提及 Microcin J25
- `train-309`：`ACCURATE`
- `train-694`：`NOT_ACCURATE`，证据句未提及 claim 主体疫苗诱导反应
- `dev-528`：`NOT_ACCURATE`，抗体来源不同
- `train-760`：`ACCURATE`
- 其余双方原值一致的 11 条按一致结果裁决。

旧版回传中另有 13 条陈明进侧为“待核”；2026-10-03 最新附件已补齐这 13 条 `annotator_1_*`，其中与李云侧标签一致，但本派生版仍未擅自填写最终裁决人。`train-1212` 的双方标签现已回收，仍需保留两篇被引文献的来源标识，因此只可登记为待共识落表，不能丢失双来源留痕。

## seed=42 ReferenceErrorDetection

除既有 excluded 记录外，26 条双方均有三分类的记录已写入最终字段。师兄明确裁决：

- `RED:23`：`ACCURATE`。按引文边界，NAMD/MDFF 属于前一引用 [22]，本引文 [23] 承接 COOT 重建；被引文献支持 COOT 的模型构建/重建。
- `RED:28`：`ACCURATE`。
- `RED:30`：`NOT_ACCURATE`。

`RED:2`、`RED:6` 按师兄确认排除；`RED:10`、`RED:21` 延续原有不可用排除状态。排除记录不填写 `project_label` 或 `adjudicated_*`。

## train-1212 来源复核

这不是重复记录，而是同一 claim 对应两篇不同被引论文：

- `cited_doc_id=6493422`，PMC3103656，`SciFact_1212a_PMC3103656.xml`，SHA-256 `1B9CAE720F8D63C4DF5C09551D6AEBC950FE4189067745477685755F62D7E653`。
- `cited_doc_id=44724517`，PMC3644709，`SciFact_1212b_PMC3644709.xml`，SHA-256 `12C2C9F61CE4B9F1BB8150B251155CB010F53CB2E688A75C7F0E541BACADFB8E`。

两篇论文题名不同，分别讨论 KLF2 对多微生物感染/内毒性休克和急慢性炎症的调控；已在裁决版工作簿的补证说明页增加文献/文件标识。师兄未对该条提供独立三分类，故保留待核。

## 输出

- seed42 裁决版：`02_数据源核查/数据源核查表_seed42_双方裁决_2026-10-03.xlsx`
- demo30 裁决版：`03_示范修复/demo30_双方裁决_2026-10-03.csv`

两份输出均已进行公式/字段检查；原始双方值仍保留，裁决字段单独填写。
