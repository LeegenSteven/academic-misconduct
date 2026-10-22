# PDF20 双人复核导入与验收汇总

2026-10-21。本工具对应 10 月 19 日任务书的双方初判、分歧裁决、失败解释拦截和四类结果分别统计。仅是后续处理工具，不调用模型，不签署实际人工意见，也不修改 v2 Test、45 条分析表或既有 PDF 运行收据。

## 当前完成边界

- 工具和 14 项模拟回归已在李云本地通过，模拟记录只在内存或自动清理的临时目录中存在。
- 2026-10-22：首批5点已生成真实模型结果，其余15点未运行。工具已核验固定20行assembled记录并生成双方各20行draft表，实际提交0条，验收数没有增加。
- 原严格工程结果1/5；另有仅去外层json围栏的离线补充诊断3/5，未替换原始解析结果。参见[实际首批与复核材料](../../results/route1_qwen38_v3/2026-10-25/pdf_demo/first5_A100_2026-10-22/README.md)。
- 原 PDF20 迁移包在 A100 主机的 CPU 检查已通过；本次新增复核工具尚未上传服务器或 GitHub，原迁移包及其哈希不变。
- 人工范围确认仍是推理前的单独步骤。本工具处理推理后的结果复核，不代替范围确认。

## 运行前提

需要原入口 `assemble` 生成的固定 20 行 `records.jsonl`，以及同一批 `runtime_plan.json`。不得把 CPU 草稿、候选检索状态或模拟响应填充成真实结果。当前不应为试用工具而伪造这份真实结果。

工具对每条记录复算解析结果、核对模型角色、revision、adapter、实际 token 指纹和原始响应关联；已宣称工程成功但缺少实际阶段证明的记录会被拒绝。以上是记录一致性校验，不是独立的权重重载或 GPU 复演，也不是对签名人的密码学认证。

## 之后取得真实结果时使用

从仓库根目录执行。下面 `/path/to/` 是需替换的实际路径，不是现在让 A100 执行的命令。

```bash
python code/ly/route1_pdf_review_v3.py init \
  --runtime-plan /path/to/runtime_plan.json \
  --records /path/to/assembled/records.jsonl \
  --output-dir /path/to/new_review_templates
```

生成 `review_liyun.jsonl` 和 `review_chenmingjin.jsonl`，每份 20 行。初始 `status=draft`，时间、回复来源、预测暴露情况、判断及依据均为空；姓名只是分工标签，不算确认或签字。

每位实际复核者填写本人文件，保留全部 20 行；本次没复核的行仍为 draft。完成一条时改为 `status=submitted`，填写带时区 `reviewed_at`、真实意见来源 `review_source`、`prediction_seen`。`assessments` 的各项为：

- `document_identity_valid`：文献身份与引用目标是否正确。
- `citation_scope_valid`：当前目标标记对应的主张范围是否正确。
- `location_valid`：选中证据的逐字原文、文献、页码和 bbox 是否有效。
- `explanation_semantic_valid`：理由的对象、方向、数量、条件是否得到证据支持。
- `judged_label`：有依据的人工三标签判断；未决保留 null。

前四项填 true、false 或 null，标签只用 ACCURATE / NOT_ACCURATE / IRRELEVANT / null。每个非空判断都必须在 `basis` 的同名字段写独立依据，指明证据编号、源材料位置或具体差异。不得把候选缺失自动解释成 IRRELEVANT。没有实际合法解释输出时，不能把定位或解释语义写成通过。

```bash
python code/ly/route1_pdf_review_v3.py merge \
  --runtime-plan /path/to/runtime_plan.json \
  --records /path/to/assembled/records.jsonl \
  --review-liyun /path/to/returned/review_liyun.jsonl \
  --review-chenmingjin /path/to/returned/review_chenmingjin.jsonl \
  --output-dir /path/to/new_reviewed_output
```

每条意见绑定整份原始结果文件和该条完整记录的 SHA-256，不能套用到换过输入、候选、理由或响应的新运行。未变更的其他行也不能绕过整份结果文件的版本绑定。原意见、原响应始终保留，输出目录必须为新目录并位于原收据/复核输入目录之外。

## 分歧与解释展示

双方都明确填写的同一项意见一致时，记录为双方一致。一方未填、两方不同，都不会自动取平均、听从模型或取其中一方。

有分歧时生成 `adjudication_needed.unsigned.jsonl`，这是未签核草稿，不可直接作为裁决导入。讨论后在另一文件保留真实共同结论，填写 `status=jointly_confirmed`、带时区 `resolved_at`、需要裁决的 `decisions` 与逐项 `basis`，以及两位在 `confirmations` 中各自的确认时间和真实来源。不得删除原始初判。裁决同时绑定两份原意见行的哈希；原意见有变，旧裁决失效。只允许裁决双方已分别明确表态且确有分歧的项目，不能代填一方尚未提交的意见。

再次 merge 时增加：

```bash
  --adjudications /path/to/actual_joint_adjudications.jsonl
```

只有实际分类及解释输出证明完整，且文献身份、范围、定位和解释语义均经双方一致或有效共同裁决为通过，才将原始 `reason_unreviewed` 原样放入 `reason_for_display`。不改写模型理由，不向失败理由补默认内容。分类对错另记：错误分类可以与工程成功并存，不要求判对才计工程闭环。

## 输出及统计口径

- `records.reviewed.jsonl`：固定 20 行，保留原始分类和解释、双方原意见、裁决及分项状态。
- `summary.json`：尝试数、工程技术成功/人工核验数、定位、解释语义、分类分别统计。
- `adjudication_needed.unsigned.jsonl`：尚未解决的分歧草稿；没有分歧时为空。
- `provenance.json`：原文件、工具和派生输出哈希。

定位始终保留分母 20；未审完时正式定位率为 null，同时明确已审数、未审数及确认有效数/20 的阶段进度。20 点审完后才判定至少 16/20 是否达到 80%。解释语义通过率仅针对已明确解决的语义判断，明确已审分母；定位不通过不会自动制造语义不通过意见。分类按有正常实际预测且人工标签已解决的点计正确数/分母，未决及无有效预测另列。原始四类字段彼此独立，不把未知填成失败率 0。

本工具不读取训练数据，不改变分类 label，不设置新阈值，不重新运行或调优已冻结 Test。复核材料已有历史预测暴露，导出统一不宣称独立盲标。

## 本地验证

```bash
python code/ly/test_route1_pdf_review_v3.py
```

14 项自动测试均为模拟数据：空模板、一人意见、分类错误但工程通过、解释分歧、双方裁决及过期裁决、未知/重复 ID、错人员、旧记录哈希、缺依据/时间/暴露信息、16 点不能缩减分母、无效解释、模拟阶段、原始响应篡改和 CLI 原文件保护等。通过这些测试只证明工具逻辑；不增加任何真实复核、GPU 运行或闭环完成数量。
