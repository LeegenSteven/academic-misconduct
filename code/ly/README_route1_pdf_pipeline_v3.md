# PDF v3 受控运行入口

当前说明更新于2026-10-25。本入口连接固定20点的两篇真实PDF、范围和候选检索、预选Mbio分类器、独立官方底座解释、校验及JSONL/CSV导出。两批A100实际运行已完成：分类和解释各18个不同点，另有第16点一次解释补跑；第1/15点按确认口径暂缓。实际结果、失败及后续版本以[固定20点总表](../../results/route1_qwen38_v3/2026-10-25/pdf_demo/固定20点进度总表.md)为准。旧入口和历史接入收据保留，不能用2026-10-21的开发状态代替当前状态。

## 交给另一人复演之前

现有材料可恢复原运行来源，但**原13点资源包不能原样充当另一人的启动入口**：`route1_pdf_remaining13_resource_trial_20261024.pyz`将请求和后端的operator固定为“李云”，`--launch`还固定使用旧run01日志。改输出目录不足以解决执行人记录和日志冲突，也不能事后手改元数据冒充新执行人。

现已准备[13点复演入口](route1_pdf_remaining13_replay_20261025.py)，本地无模型检查通过，SHA256为`0f8f4ea785c6ae48e9eb8aa2e04eb6ec36b25c77d5aef06214d2598fe1bcb616`。它要求真实operator、新输出和新日志；分类和解释分别在独立进程中运行。依赖原资源包的SHA256固定为`4b21f1269bd808491cdcaf9d67ef82a2c706997ae39ed42079c1c4dc4444e66b`。原包内run函数仅将两处固定“李云”替换为传入执行人，完整AST往返核对其余函数内容不变；启动路径和复演来源记录单独留痕。

本入口只复演**原13点r2输入、原512-token生成、原严格解析**，不采用后来的v4解析或第16点紧凑v2提示，不与它们合并计分。执行人姓名按本人填写记录，不据此自动认证身份或形成共同签核。**2026-10-25李云已完成A100本人13点复跑并回传；两阶段响应与原运行逐字节一致，原严格失败同样保留。** 实际结果见[当前总表](../../results/route1_qwen38_v3/2026-10-25/pdf_demo/固定20点进度总表.md#李云本人13点复跑已完成2026-10-25)；该次不计另一人复演。 不得重用旧启动命令、覆盖旧日志或更改已完成Test。

实际资源政策也与初版不同：首批5点采用已留痕的30000 MiB门槛；后13点采用实际空闲减2048 MiB、最多整卡95%的本进程PyTorch限额，取消35000 MiB启动门槛。后者不覆盖全部外部分配或保证共享卡运行成功。当前没有统一的新20点运行冻结，不能把两个资源变体说成同一原始执行代码。

以下`/path/to/`命令是初版接口说明，不是已核对的当前A100复演命令。具体来源、生成与解析版本、执行人及新输出路径对齐后，才交接实际运行。

### 13点复演的完整阶段命令（由实际执行人操作）

以下保留恢复命令。李云本人本次已执行完成，当前无需再次启动；另一实际执行人有明确复演安排时，填写真实姓名并使用新的输出目录。原pyz保持不变：

```powershell
scp -P 7002 -o ServerAliveInterval=30 -o ServerAliveCountMax=6 "C:\Users\y\Desktop\学术引用不端\_route1_test_pair_publish_20261019\code\ly\route1_pdf_remaining13_replay_20261025.py" admire@s2.admirecn.de:/home/admire/
```

A100中先核验与预检。`read`必须由实际执行人填写，不能由李云重跑后填写他人姓名；若只是本人重跑，也不能记为跨人员完成。预检失败时先保留报错，不继续启动。

```bash
printf '%s\n' '0f8f4ea785c6ae48e9eb8aa2e04eb6ec36b25c77d5aef06214d2598fe1bcb616  /home/admire/route1_pdf_remaining13_replay_20261025.py' | sha256sum -c -
python /home/admire/route1_pdf_remaining13_replay_20261025.py --self-check
read -r -p '本次实际执行人姓名: ' PDF_REPLAY_OPERATOR
PDF_REPLAY_OUT="$HOME/route1_pdf_independent_replay_$(date -u +%Y%m%dT%H%M%SZ)"
nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv
python /home/admire/route1_pdf_remaining13_replay_20261025.py --preflight --operator "$PDF_REPLAY_OPERATOR" --stage both --gpu 2 --output-root "$PDF_REPLAY_OUT"
```

仅在上述预检通过、实际GPU2资源可用且该次执行安排确定后启动。`--launch`使用nohup与独立会话，SSH断开不要求重新启动。两个角色各一次，不自动重试；任一阶段执行非0时停止，不继续下一角色。

```bash
python /home/admire/route1_pdf_remaining13_replay_20261025.py --launch --operator "$PDF_REPLAY_OPERATOR" --stage both --gpu 2 --output-root "$PDF_REPLAY_OUT"
tail -n 30 -F "${PDF_REPLAY_OUT}.run.log"
```

详细逐点日志分别在`$PDF_REPLAY_OUT/classifier_execution/classifier/run.log`与`$PDF_REPLAY_OUT/explainer_execution/explainer/run.log`。查看日志的Ctrl+C只退出tail。新会话应沿用启动时打印的OUTPUT_ROOT，不重新创建新运行。结束后先检查：

```bash
cat "$PDF_REPLAY_OUT/replay_summary.json"
cat "$PDF_REPLAY_OUT/classifier_execution/classifier/exit_code.txt"
cat "$PDF_REPLAY_OUT/explainer_execution/explainer/exit_code.txt"
tar -czf "${PDF_REPLAY_OUT}.tar.gz" -C "$(dirname "$PDF_REPLAY_OUT")" "$(basename "$PDF_REPLAY_OUT")" "$(basename "$PDF_REPLAY_OUT").run.log" "$(basename "$PDF_REPLAY_OUT").launch.json"
sha256sum "${PDF_REPLAY_OUT}.tar.gz"
```

若提前失败，后阶段文件可能不存在，按实际缺失保留；阶段退出0只表示结果收集正常，不意味着原严格解释全部通过。从Windows PowerShell下载时，把`实际OUTPUT_ROOT`替换为该次启动打印的完整目录名：

```powershell
scp -P 7002 -o ServerAliveInterval=30 -o ServerAliveCountMax=6 "admire@s2.admirecn.de:实际OUTPUT_ROOT.tar.gz" "C:\Users\y\Desktop\学术引用不端\10.19-11.2\"
```

李云本次已执行并核对固定13点覆盖、模型角色、release/token指纹、输出与失败状态；两份响应文件与原运行逐字节一致。后续实际复演仍按真实执行人记录，不自动增加人工语义通过或20点验收数量。其他A100或路径需要逐项换成按哈希恢复的实际路径，不能只改机器名后直接运行。

## 支持范围

当前支持已登记的 20 点、10 对真实 PDF。按两 PDF 的 SHA-256 和既有目标引用标记匹配，严格保留原文位置及去重键。对于未知 PDF 对，返回 `pair_not_in_registered_scope`；不会猜测引用对象或造出新引用点。任意新 PDF 的自动引用抽取、身份确认与建档仍不属于本轮已完成能力。

本批领域已预选为 biomedicine，分类只用 Mbio checkpoint-100。独立解释模块在首次新预测之前固定为同一官方底座、不加载 adapter；它不接收分类标签，也不改写分类结果。解释是官方底座的输出，不能称为 Mbio 学会解释。超出本批领域或换 adapter 的输入会停止；Mscv 及原有 6 个 Test 单元保持原状。

所有命令要求新输出目录，不覆盖已有运行。来源包、2026-10-20 输入准备目录均只读。不得将单元测试模拟响应作为实际模型结果。

## 初版分阶段接口说明（历史示例）

原入口和材料已迁移A100，20点、40组token指纹的CPU核验通过；后来两批真实GPU运行和第16点补跑见总表。范围确认和原release均保留。下列变量仍为初版占位示例；不要据此重新冻结已确认范围，也不要按“尚未运行”重启旧任务。

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

需要PyMuPDF 1.28.2、Transformers 5.8.0；独立依赖目录可用`--pymupdf-dir`、`--tokenizer-deps`指定。CPU检查不加载模型权重或使用GPU；依赖可能间接导入torch，不能把“已导入torch”与“已初始化CUDA/运行模型”混同。`runtime_plan.json`分别保存分类和解释token ID指纹、输入哈希及预算。既有输入未变的通过记录复用，CPU成功不自行释放新输入。

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

初版后端只显示一张指定GPU，并要求至少35000 MiB空闲。这是旧代码条件，后续实际资源变体见本页开头，不能继续当作当前统一要求。量化与解码保持4-bit NF4、bf16、关闭reasoning、greedy、生成512、总预算5120、不截断；第16点紧凑解释补跑的输入版本另列。GPU执行核对token数及完整指纹，并记录placement、adapter、环境和版本。失败不自动重试或切换模型设备。

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
