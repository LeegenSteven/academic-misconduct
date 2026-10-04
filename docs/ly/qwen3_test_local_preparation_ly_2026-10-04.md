# Qwen3 Test 本地准备与输入核验 v1

日期：2026-10-04

## 当前状态

陈明进已确认没有历史 Qwen3 606 条 Test 输出、冻结配置和运行日志；A100 当前也无法连接。因此本记录只完成本地输入核验和重跑准备，不启动模型、不生成伪造的 Qwen3 Test 结果。

## 已核验的本地输入

- Test 输入：606 条，ID 为 0–605，唯一 ID 606 个。SHA-256：`B458C9EA7ACB8630144652E732A846AFDFAC29230C20A61E402C628929890B50`。
- 当前冻结标签：606 条，ACCURATE 386、NOT_ACCURATE 167、IRRELEVANT 53。SHA-256：`68CFA053BAA176093446197EBFB131925B1A27E3FAD8DBFA7170B46DE7A159CA`。
- 独立重算标签文件：606 条，SHA-256：`4AD6C6BB06F0A3161993F68E79815A4735328E6AD4A914D57A252680CD5A7ADE`。
- 冻结标签与独立重算文件有 3 条记录不一致：claim_id 482、487、495；三条在冻结文件中为 IRRELEVANT，在独立重算文件中为 NOT_ACCURATE。这个差异必须在重跑前固定口径，不能静默覆盖。
- 已有 606 条结果是 MultiVerS step2141 基线，预测文件 SHA-256：`2864B0CC9AC7B6FA4C43D0972C302C85123C83940C7F752D3005419125D5507C`；不能改称 Qwen3。

## 仍缺少的复现材料

- Qwen3 Test 对应的 `model_inputs_test.jsonl`，包括候选证据构造方法和输入哈希。
- Qwen3 模型/量化版本与完整 digest。历史记录只证明当时存在 `qwen3:latest`，不能证明当前服务器仍是同一版本。
- 冻结 system/user prompt、模板哈希、解码参数、随机种子。
- A100 环境、依赖版本、运行日志、raw response 和资源/时间登记。

## 服务器恢复后的执行顺序

1. 先确认 A100 可用、模型 digest 与运行环境；登记 GPU、预计时间和输出目录。
2. 固定 Test 输入 SHA-256 和标签口径，先解决 482/487/495 三条差异。
3. 生成并核对 `model_inputs_test.jsonl`，先跑少量 smoke test，确认 failure_status 全为 null。
4. 再运行 606 条全量；保留原始输出、日志、配置和失败记录。
5. 本地统一计算 Accuracy、Macro-F1、各类 P/R/F1、NEI 分母和错误方向。

## 目前可以继续的本地工作

- 完成 Test 输入与标签的版本/哈希登记；
- 准备统一评测脚本和对照表结构；
- 继续证据定位和 natural 试标集交付；
- 不把 MultiVerS 结果、Qwen3 Dev 结果或 SciCiteVal 结果当作 Qwen3 Test。
