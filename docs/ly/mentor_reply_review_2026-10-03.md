# 师兄最新回传核对记录（2026-10-03）

## 来源与留痕

- 原始回传文件：`数据源核查表_seed42_李云人工确认版_全文补定位_v19_2026-10-02(2).xlsx`
- 原始回传文件 SHA-256：`6F3E75C6CA6081B0DFA5FF7B35F0D85CEB9499664AD4AC7B570D9CB7B99B4010`
- 合并基线：`数据源核查表_seed42_双方裁决_许可更正_v4_汇总修正_2026-10-03.xlsx`
- 合并文件：`data/processed/seed42_mentor_reply_merged_v5_2026-10-03.xlsx`

## 本次实际变化

师兄回传补齐了原来缺失的 13 条 SciFact `annotator_1_*` 字段：

`SciFact:train-389`、`SciFact:train-876`、`SciFact:train-486`、`SciFact:train-361`、`SciFact:dev-238`、`SciFact:train-96`、`SciFact:train-91`、`SciFact:train-817`、`SciFact:train-81`、`SciFact:train-777`、`SciFact:train-20`、`SciFact:train-1212`、`SciFact:train-1195`。

这些记录的双方标签均已填齐；不改 `original_label`、来源字段、证据文本、哈希、`project_label` 或已有 `adjudicated_*`。RED 没有新增三分类标注；`RED:2`、`RED:6` 的“待核/撤稿”状态仍按不可用来源保留，不进入正式试标。

## 当前双方结果

- SciFact：24 条双方标签一致，6 条不一致。
- RED：28 条有双方三分类标签，其中 25 条一致、3 条不一致；`RED:2`、`RED:6`、`RED:10`、`RED:21` 均为不可用/排除，所以正式可用的 26 条中为 23 条一致、3 条不一致。`RED:2`、`RED:6` 仍保持空三分类。
- 双方分歧记录共 9 条；这 9 条在 v4 中已经有师兄裁决字段，本版继续保留双方原值和既有裁决，不重复标成待裁决：
  - SciFact：`train-78`、`train-788`、`train-309`、`train-694`、`dev-528`、`train-760`
  - RED：`RED:23`、`RED:28`、`RED:30`

双方分歧集中表现为：师兄 `annotator_1_label=NOT_ACCURATE`，李云 `annotator_2_label=ACCURATE`。双方原值保留，v4 中已有的裁决字段继续保留。

真正尚未登记的是新增的 13 条 SciFact 一致记录：双方标签相同，但本版不擅自填写裁决人；它们已单列在“一致但待登记_2026-10-03”工作表。

## 校验结果

- 两个主数据表各 30 条，SciFact 的 `annotator_1_*` 已无空缺；RED 的撤稿/不可用记录按规则保留空三分类。
- 新增的“师兄回传核对”“待裁决分歧”和“一致但待登记”工作表已写入合并文件。
- 公式错误扫描：0 条。
- 下一步是按项目既定共识规则登记这 13 条一致记录；9 条分歧不再重复向师兄索要标签，除非要复核既有裁决理由。
