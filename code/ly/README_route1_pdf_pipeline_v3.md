# PDF v3 受控运行入口

2026-10-21。本入口连接固定 20 点的两篇真实 PDF、范围和候选检索、预选 Mbio 分类器、独立官方底座解释、校验及 JSONL/CSV 导出。本轮只完成本地开发与 CPU 核验，GPU 后端尚未在 A100 实测，不能据此宣称真实闭环已经完成。旧 `run_route1_pdf_v3.py` 及其接入检查收据保留不变。

## 支持范围

当前支持已登记的 20 点、10 对真实 PDF。按两 PDF 的 SHA-256 和既有目标引用标记匹配，严格保留原文位置及去重键。对于未知 PDF 对，返回 `pair_not_in_registered_scope`；不会猜测引用对象或造出新引用点。任意新 PDF 的自动引用抽取、身份确认与建档仍不属于本轮已完成能力。

本批领域已预选为 biomedicine，分类只用 Mbio checkpoint-100。独立解释模块在首次新预测之前固定为同一官方底座、不加载 adapter；它不接收分类标签，也不改写分类结果。解释是官方底座的输出，不能称为 Mbio 学会解释。超出本批领域或换 adapter 的输入会停止；Mscv 及原有 6 个 Test 单元保持原状。

所有命令要求新输出目录，不覆盖已有运行。来源包、2026-10-20 输入准备目录均只读。不得将单元测试模拟响应作为实际模型结果。

## 分阶段使用

原入口和材料现已通过独立迁移包上传 A100，并完成 20 点、40 组 token 指纹的 CPU 核验；没有执行 GPU 命令。以下恢复命令仍需换成迁移后的实际路径，并先完成真实范围确认。新增加的双人复核工具仍只在李云本地；本轮没有上传 GitHub。

```bash
cd /home/admire/academic-misconduct-route1
SOURCE=/path/to/路线一PDF独立清单_20261020
PREP="$PWD/results/route1_qwen38_v3/2026-10-25/pdf_demo/scope_and_input_preparation_2026-10-20"
MODEL=/home/admire/models/Qwen3.8-27B
CHECK=/path/to/new_runtime_preparation
PY=/opt/miniconda3/bin/python
```

1. 只读实际 PDF 和 tokenizer 的 CPU 检查：

```bash
CUDA_VISIBLE_DEVICES="" "$PY" code/ly/route1_pdf_pipeline_v3.py prepare-runtime \
  --source-root "$SOURCE" --prepared-dir "$PREP" \
  --model-path "$MODEL" --output-dir "$CHECK"
```

需要 PyMuPDF 1.28.2、Transformers 5.8.0；本地独立依赖目录可用 `--pymupdf-dir`、`--tokenizer-deps` 指定。此命令不导入 torch 或加载模型权重。`runtime_plan.json` 中分别保存分类和解释的实际 token ID 指纹、输入哈希及预算，全部候选保留。CPU 成功不释放输入。

2. 两篇 PDF 的明确调用示例：

```bash
CUDA_VISIBLE_DEVICES="" "$PY" code/ly/route1_pdf_pipeline_v3.py inspect-pair \
  --source-root "$SOURCE" --prepared-dir "$PREP" \
  --citing-pdf "$SOURCE/sources/PMC8371605.1/PMC8371605.1.pdf" \
  --cited-pdf "$SOURCE/sources/PMC6324056.1/PMC6324056.1.pdf" \
  --output-dir /path/to/new_pair_check
```

该调用检查真实 PDF、引用方向和登记点，不执行推理。同一对 PDF 中的不同物理标记会分别列出；其中仍可能有范围暂停点。已保存本地成功示例及交换两 PDF 后的范围不匹配失败示例，二者均不计实际模型闭环。

3. 确认范围后冻结执行配置：

`scope_confirmation_template.json` 默认全部为空/未确认，不能直接运行。它只记录引用范围确认，不是三分类标签。由实际确认者填写 `confirmed`、`reviewer`、带时区 `reviewed_at` 和 `review_source`；第 1、15 点另需 `hold_resolution`。不得把辅助范围建议或自动测试签名冒充人工确认。范围需要改动时先生成新的准备版本，重算受影响输入及预算，不能只改表格中的 SHA。

```bash
"$PY" code/ly/route1_pdf_pipeline_v3.py freeze \
  --source-root "$SOURCE" --prepared-dir "$PREP" \
  --runtime-plan "$CHECK/runtime_plan.json" \
  --confirmations /path/to/actual_scope_confirmations.json \
  --output-dir /path/to/new_release
```

默认检查固定 20 点的确认。首次小批可在新预测前用多个 `--case-id` 明确选定已确认点；全批 20 点仍保留，其余点不得从最终分母消失。不得看预测后更换点。确认绑定当前范围、模型输入、代码和准备文件哈希；任一变化需新版本。

4. 之后才运行分类与解释。先确认所选 GPU 的资源可用，不停止其他人的进程：

```bash
RELEASE=/path/to/new_release/release.json
SUMS=/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_model_weightcheck_20261016/official_sha256sums.txt
MBIO=/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/checkpoint-100

"$PY" code/ly/route1_pdf_pipeline_v3.py run-classifier \
  --source-root "$SOURCE" --prepared-dir "$PREP" --release "$RELEASE" \
  --model-path "$MODEL" --weights-manifest "$SUMS" --adapter "$MBIO" \
  --gpu 2 --operator 李云 --output-dir /path/to/new_classifier_run

"$PY" code/ly/route1_pdf_pipeline_v3.py run-explainer \
  --source-root "$SOURCE" --prepared-dir "$PREP" --release "$RELEASE" \
  --model-path "$MODEL" --weights-manifest "$SUMS" \
  --gpu 2 --operator 李云 --output-dir /path/to/new_explainer_run
```

实际后端在加载前核对官方四个 tokenizer/config 文件、已归档官方 SHA 清单及全部 18 个权重分片；分类另查 adapter 权重和配置哈希。清单 SHA-256 为 `3ebc83ee545cc54cb2558d805802d4a4e9da42c316d1b248846debee545b99c9`，Mbio 权重为 `0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09`。官方底座 revision 固定为 `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`。

后端只显示一张指定 GPU，加载前要求至少 35000 MiB 空闲；4-bit NF4、bf16、关闭 reasoning、greedy、生成 512、总预算 5120、不截断。实际 GPU 上会再核对 token 数和完整 token ID 指纹，并记录 placement、实际 adapter、GPU 环境和版本。失败不自动重试，不自动切换模型或设备。

每阶段保存 `run.log`、`responses.jsonl`、`run_metadata.json`、`exit_code.txt`。原始响应和生成 token IDs 保留；`exit_code=0` 表示阶段正常收集结束，不表示每条解析、语义或人工验收通过。遇到可捕获的运行异常，保留此前结果，后续点记为未尝试；遇到外部强制中断或断电，未完成的运行记录不允许被当作已完成导出。换新目录恢复，旧记录不覆盖。

5. 汇总为 20 点结果：

```bash
"$PY" code/ly/route1_pdf_pipeline_v3.py assemble \
  --source-root "$SOURCE" --prepared-dir "$PREP" --release "$RELEASE" \
  --classifier-run /path/to/new_classifier_run \
  --explainer-run /path/to/new_explainer_run \
  --output-dir /path/to/new_assembled_records
```

得到 `records.jsonl`、`records.csv` 和 `summary.json`。缺少一个阶段时可暂不传该阶段路径，仍导出全部 20 点并记录未运行，不能把缺少解释改成 IRRELEVANT 或删掉已取得的分类标签。证据不足返回独立失败状态，不是第四类标签。

## 解释校验与验收口径

解释只允许选择实际候选编号。摘录必须是候选原文中的唯一连续片段，映射回同一被引 PDF 的原始码点区间及块级 bbox。5′/3′ 修订保留模型摘录和原文摘录两层，二者的偏移映射不混淆。编号越界、改写摘录、含混定位均拦截。

即便摘录及 JSON 合法，reason 仍存入 `reason_unreviewed`，`reason_for_display` 留空，解释状态为待人工语义核查。程序不能仅凭字符串匹配判断理由涉及的对象、方向、数量和条件是否全部得到支持。新增的[双人复核回传工具](README_route1_pdf_review_v3.md)在本地通过 14 项模拟检查；需先取得真实 assemble 结果及双方实际复核意见，再导入核查和裁决，符合条件时才解锁原理由展示。当前尚未导入真实双方复核，不能把工具开发通过当作语义验收。

`confidence` 和三个 `score_*` 均为 null。分类标签来自分类器；解释来自单独的底座模型，来源分别记录。工程技术成功可与分类错误并存；定位人工有效数、解释语义合格数、分类正确数/已裁决分母及未决数分别统计。没有人工结果时保持未知，不能用 0 代替尚未测得的比例。最终定位分母仍为固定 20，至少 16 点经人工确认有效才达到 0.80。

## 回归检查

```bash
"$PY" code/ly/test_route1_pdf_pipeline_v3.py \
  --source-root "$SOURCE" --prepared-dir "$PREP" \
  --runtime-plan "$CHECK/runtime_plan.json" --pymupdf-dir /path/to/pymupdf_1.28.2
```

15 项 CPU 回归覆盖草稿暂停、范围及哈希绑定、固定分母、失败状态、证据越界/改写、转写偏移、模拟运行异常、原始响应篡改、adapter 角色和两 PDF 方向等。模拟响应仅出现在自动清理的临时目录，显式标记 simulation，不加载权重、不使用 GPU、不计真实闭环。本轮真实本地检查记录在 `results/route1_qwen38_v3/2026-10-25/pdf_demo/runtime_preparation_2026-10-21/`。
