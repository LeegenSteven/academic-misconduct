# Route2 5 条共同样本最终裁决记录（v1，2026-10-11）

## 最终文件

`route2_semantic_joint_adjudication_full_v1_2026-10-11.csv` 共 5 条，按 `edge_id` 对齐了李云侧独立标注、陈明进原始回传和共同裁决字段。

- 最终 ACCURATE：3 条（edge:0013、edge:0034、edge:0104）
- 最终 NOT_ACCURATE：2 条（edge:0062、edge:0082）
- 最终 IRRELEVANT：0 条
- 证据状态：5 条均为“已定位”
- `edge:0082` 和 `edge:0104` 的最终 `joint_*` 字段来自陈明进回传的最终裁决文件；没有覆盖双方原始标注。

## 输入留痕

- 陈明进最终两条裁决文件：`route2_semantic_joint_adjudication_final_v1_2026-10-11.csv`
- 陈明进最终文件 SHA-256：`a54071b5d318ee42d36bac0b667478fc9cc588d794be80e7eef2b16f8c3e0202`
- 5 条最终合并文件 SHA-256：`e73bee4e76ac231b733c373a83780253fe55b2e42706572a20bea6b9311a79d0`

## 质量检查

- 行数为 5，`edge_id` 无重复。
- 原始 citing/cited 标识字段未修改。
- 每条均有最终标签、证据状态、稳定定位和裁决理由。
- 标签仅使用 `ACCURATE`、`NOT_ACCURATE`、`IRRELEVANT`；没有把证据缺失记录强行标为 `IRRELEVANT`。
