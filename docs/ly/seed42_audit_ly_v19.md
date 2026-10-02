# 李云 seed=42 来源核查快照

日期：2026-10-02
状态：李云侧阶段结果，未完成双人裁决

## 文件

- 数据快照：`data/processed/seed42_source_audit_ly_v19.csv`
- 完整核查工作簿：`data/processed/seed42_source_audit_ly_v19.xlsx`
- 快照 SHA-256：`2267D754B53BA51FE1FB6A660445B7DF800C3780943E2CF109731E9E6D245BE8`
- 工作簿 SHA-256：`0BEC646E34E0ED9A61DC76121A6975A5E3A62010E1E71432F28A4AF8F977711B`
- 重建脚本：`scripts/fetch_seed42_sources.py`
- 校验脚本：`scripts/validate_seed42_snapshot.py`

## 结果摘要

| 来源 | 样本 | 李云侧证据状态 | 李云侧初判 | 备注 |
|---|---:|---|---|---|
| SciFact | 30 | 30 条已定位 | ACCURATE 16、NOT_ACCURATE 12、IRRELEVANT 2 | 原始 `evidence_status` 仍保留；记录为 `constructed` |
| ReferenceErrorDetection | 30 | 28 条已定位、2 条待定位 | ACCURATE 8、NOT_ACCURATE 10、IRRELEVANT 10；2 条空白 | RED:2、RED:6 因不可用/撤稿状态排除 |

`project_label`、`adjudicated_label` 以及其他裁决字段均为空。这个快照不能作为已完成的双人标注集，也不能直接计入正式新来源试标集。

## 许可和复现边界

- SciFact 使用官方 release 数据；claims 与 corpus 的许可、版本和 SHA-256 在 CSV 的每行 `license_name`、`file_version`、`file_hash` 中保留。
- ReferenceErrorDetection 使用官方仓库数据和许可入口；完整原始文件只通过 `fetch_seed42_sources.py` 下载到本地 `data/raw/`，不提交到 Git。
- 快照含论文引用文本、DOI 和证据定位，当前仅用于私有仓库内部复核；对外发布前需再次检查数据集许可和引用文本的再分发边界。
