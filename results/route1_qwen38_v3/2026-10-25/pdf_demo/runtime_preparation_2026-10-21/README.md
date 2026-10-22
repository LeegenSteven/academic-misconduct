# 本地 v3 运行入口准备与核验

2026-10-21。对应任务书中李云负责的“统一调用入口”。本轮已完成本地代码和 CPU 检查；没有连接 A100、没有加载模型权重、没有新分类或解释输出，也没有填写任何人的标签或裁决。

| 项目 | 本轮状态 |
| --- | --- |
| 固定批次 | 20 个引用点、10 对 PDF、200 条候选，均保留 |
| 两篇 PDF 接入 | 对已登记 PDF 检查身份、引用方向和原文位置；成功和方向不匹配实例已落盘 |
| 分类阶段 | 预选 Mbio checkpoint-100，保留 label-only 目标；不因解释缺字段重训 |
| 独立解释阶段 | 首次预测前固定官方底座、无 adapter；不接收分类标签，不更改分类结果 |
| 预算 | 分类 20/20，最长 4692；解释 20/20，最长 4666；均含 512 生成预算，总上限 5120，不截断 |
| 自动回归 | 15 项通过，含合法模拟流程及错误分支；模拟不算真实模型运行 |
| 范围暂停 | 第 1、15 点疑问保留；范围确认模板全部未签，尚无任何输入释放执行 |
| 实际模型、工程闭环、人工语义 | 本轮均未验收，正式定位率和分类准确率未知 |

入口将分类、定位、解释和工程状态分开。证据编号或摘录错误会拦截；解释摘录合法也只标“结构与摘录通过、待人工语义核查”，不自动接受理由或向用户展示为已审核说明。证据不足保留失败状态，不转为 IRRELEVANT。失败和未尝试的点继续留在固定分母中。

## 文件索引

- [完整使用方式与支持范围](../../../../../code/ly/README_route1_pdf_pipeline_v3.md)
- [统一 CLI 入口](../../../../../code/ly/route1_pdf_pipeline_v3.py)、[A100 后端](../../../../../code/ly/route1_pdf_hf_backend_v3.py)、[回归检查](../../../../../code/ly/test_route1_pdf_pipeline_v3.py)
- [实际 CPU 汇总](CPU_check_summary.json)、[CPU 日志](local_CPU_preparation.log)、[15 项回归日志](regression_tests.log)
- [运行计划和逐点双阶段预算](runtime_plan.json)、[解释输入草稿](explanation.draft.inputs.jsonl)
- [范围确认空模板](scope_confirmation_template.json)：当前全空/未确认；不是新的盲标表，不用现在再发陈明进
- [两 PDF 成功接入实例](examples/registered_pair_check.json)、[交换方向后的失败实例](examples/reversed_pair_check.json)、[草稿被暂停的检查](examples/pending_scope_freeze_check.json)
- [最终核验与完整性记录](delivery_integrity.json)

## 接下来

陈明进回复两处范围问题后，保留原始回复；需要改范围时生成新准备版本。范围确认应由实际确认者留名和依据，不把工具建议代填成人工签字。再冻结输入、代码、模型和运行参数，迁移到 A100 做固定小批实测。新代码目前只在本地，尚未上传 GitHub 或服务器。

当前能力限于已有清单的 PDF 对；未知 PDF 仍需先建档、确认引用位置。GPU 加载和真实推理、双方语义核查、人工回传导入与解释展示解锁尚未完成。本目录的 CPU 成功与测试成功不能替代这些步骤，也不能写成 20 点已完成真实闭环。

来源与输入准备仍以[上轮记录](../scope_and_input_preparation_2026-10-20/README.md)为准；本轮没有修改它们。开发早期的 CPU 收据保留在 `../history/runtime_preparation_initial_20261021/`，当前以本目录为准。
