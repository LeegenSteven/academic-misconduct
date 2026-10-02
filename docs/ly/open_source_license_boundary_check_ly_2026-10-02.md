# 开放来源许可边界核查（李云侧）

日期：2026 年 10 月 2 日

## 结论

当前可以确认的是数据集数据库层面的许可；不能把代码仓库许可、数据库许可和被引论文文本的权利混写。正式新来源试标可在私有研究环境中继续做元数据和必要证据核验，但对外提交前仍需保留来源与许可说明，不直接再发布未确认可再发布的全文。

## 来源清单

| 来源 | 已核实的许可/权利 | 当前可做 | 尚需保留的边界 |
|---|---|---|---|
| SciFact claims | 项目记录为 CC BY 4.0；来源入口和 release/commit、SHA-256 已留痕 | 可在项目内部使用并按许可保留署名 | claims 中的引用文本仍需保留来源和版本；不能把构造 claim 当自然引用 |
| SciFact corpus / S2ORC 摘要 | 项目记录为 ODC-By 1.0 | 可在项目内部按 ODC-By 记录和署名 | ODC-By 数据库许可不自动覆盖其中每篇论文内容的其他权利；仅保留必要证据片段和定位 |
| ReferenceErrorDetection 数据库 | 本地 `ReferenceErrorDetection_LICENSE.txt` 明确为 ODC Attribution License（ODC-By） | 可在项目内部按 ODC-By 记录和署名 | 数据中的 PubPeer 陈述、论文摘要和被引论文文本可能有独立权利；不因数据库许可自动获得全文再发布权 |
| ReferenceErrorDetection 代码仓库 | 当前本地核查未把代码许可文件与数据许可混在一起确认 | 代码许可需单独引用其 LICENSE 文件 | 在未核实代码 LICENSE 前，不把“Apache 2.0”写入数据许可字段 |
| 被引论文全文、出版社页面、作者公开 PDF | 逐篇依其页面或文件声明判断 | 可记录 DOI、来源入口、页段和必要短摘 | 付费全文、撤稿论文和无明确再发布许可的 PDF 不进入项目数据包的全文再发布 |

## 已核对文件

- `02_数据源核查/原始下载/ReferenceErrorDetection_LICENSE.txt`
- `02_数据源核查/候选数据源核查说明_2026-09-29.md`
- `02_数据源核查/数据源核查表_seed42_李云人工确认版_全文补定位_v19_2026-10-02.xlsx`

`ReferenceErrorDetection_LICENSE.txt` 的 SHA-256：`11A6D83734845AD09D809667AA219857A5B985B28C258A2EEBF5677668A6BD3B`。

## 对当前表格的修正要求

当前 v19 表中 RED 的 `license_name` 仍带有“Apache 2.0（仓库代码）”的旧式合并表述。该字段不应继续作为正式数据许可结论使用。正式合并前应改成分栏记录：

1. `dataset_license = ODC-By 1.0`；
2. `code_license = 待单独核验`，并附代码仓库 LICENSE 入口；
3. `content_rights = PubPeer/论文内容另行核验；当前仅内部研究、必要短摘和定位`。

本说明不覆盖双方标注值，也不改变 `original_label`、`evidence_status`、`project_label` 或裁决字段。
