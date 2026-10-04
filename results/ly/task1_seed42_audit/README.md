# seed=42 两个数据源逐条交付说明

更新时间：2026-10-04

- SciFact：30 条；17 条已定位并有最终裁决，13 条源文缺失/待核。
- ReferenceErrorDetection：30 条；26 条已定位并有最终裁决，4 条不可用/排除。
- 当前两个数据源合计：60 条中 43 条具备证据定位和最终裁决，17 条仍未形成合格样本。
- 逐条 CSV：
  - `seed42_SciFact_30_row_level_audit_v4_2026-10-04.csv`
  - `seed42_RED_30_row_level_audit_v4_2026-10-04.csv`
- 完整工作簿：`data/processed/seed42_adjudicated_pilot_ly_license_corrected_v4_2026-10-03.xlsx`。

字段保留双方标注、证据定位、最终裁决和空缺状态；空值代表尚未形成可用裁决，不用原始标签代替。
