# Route2 5条共同样本合并核对记录（v1，2026-10-11）

- 李云独立标注：`route2_semantic_blind_annotation_ly_v1_2026-10-11.csv`
- 陈明进原始回传：`反向选样_优先候选边_两端均含PMC全文_20261011(2).csv`
- 合并对照：`route2_semantic_merged_comparison_v1_2026-10-11.csv`
- 待共同裁决：`route2_semantic_joint_adjudication_pending_v1_2026-10-11.csv`

## 对照结果

- 5 条均按 `edge_id` 对齐，原始论文字段未改动。
- `edge:0013`、`edge:0034`：双方标签与证据状态一致（ACCURATE，已定位）。
- `edge:0062`：双方标签与证据状态一致（NOT_ACCURATE，已定位），理由表述不同，保留双方原理由，待共同归档。
- `edge:0082`：李云侧为 NOT_ACCURATE/已定位，陈明进侧为待定位，需共同裁决。
- `edge:0104`：李云侧为 ACCURATE/已定位，陈明进侧为源文缺失，需共同裁决。

合并表未擅自替双方填写 0082、0104 的共同裁决结论；待裁决表只列出需要双方确认的 2 条。

## SHA-256

- 合并对照：`8b7c0f84838c44bd096054d4ce8ee54024e44cea5bb3afb8fef28a6e75a5ccf0`
- 待共同裁决：`c5b47529854c85f5b753b1757155be3fdfd01657c7df88f311a4cee43d867383`
