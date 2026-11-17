# mbio_reproduction 归档索引（README）

Sarol 路线一 Mbio 复现核验归档，由陈明进负责，2026-10-24 生成。

| 内容 | 位置 | 说明 |
|---|---|---|
| 审计总览 | `audit.md` | 哈希对照、长度复算、等价性结论、checkpoint 来源、缺口 |
| 长度复算 | `length_report/` | 2141 条官方 tokenizer 复算结果与汇总 |
| 等价性（CPU 侧） | `equivalence_test/` | 李云 10/20 实测结论摘要 + 容差口径 |
| adapter 恢复索引 | `adapter_recovery/` | A100 路径、哈希、选择依据、重载命令 |
| 实际脚本 | `code/` | 修复后训练脚本、等价性测试脚本、复算脚本 |
| 哈希清单 | `file_hashes.json` | 本目录全部文件 SHA256 |

关键边界：CPU 等价性通过仅支持修复候选目标/更新逻辑；27B/NF4 GPU 验证与 checkpoint 保存/重载验证待 A100 执行，未完成前不宣称逐位等价、不将历史 adapter 标记为已自动修复。
