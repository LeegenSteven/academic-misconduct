# v2 数据独立交叉审阅简报

审阅范围：`build_sciciteval_inputs_v2.py`、`verify_route1_data_v2.py`、两套实际输入/gold、manifest 和冻结源。仅在 audit 目录写审阅产物；没有修改待审文件，没有重新计算全量 BM25，也没有运行模型。

结论：当前交付数据通过独立源比对，未发现阻止使用的数据错误。

- 4087 条有效样本的输入/gold 数量、逐条 ID 和顺序正确。
- SciCiteVal 1024 条有效数据的 Citation_context、Cited_content 原文、源标签和分组完全保持；10 条冲突隔离记录的原始内容和分组元数据完整保留。
- Sarol 3063 条 claim 原文、标签、gold evidence、来源歧义和证据缺失状态完全保持；30630 个候选的真实 doc_id、源文档排序、原句位置及文本均与 corpus 逐项相符。紧凑 Dxx:Sxx 编号与候选元数据一致。
- 模型可见的 system/user 与独立重建的预期字符串完全相等。输入中不再插入原始 claim_id、row_id 或真实 doc_id；真实 ID 只保留在外部关联 metadata。两套 system 均与冻结 system_prompt 哈希一致。
- 两套 builder、manifest 引用源及 system 哈希独立核验通过。总验证器对 15 个输出文件大小/哈希检查通过。
- SciCiteVal 生成器从仓库根使用默认源参数、仅将输出改到 audit/scv_reproduction 运行成功。11 个产物（包括 manifest、validation_report）与交付版本逐字节相同。
- Sarol claim_id 跨 split 不全局唯一，`(dataset, split, claim_id)` 联合键唯一。当前 JSONL 按 split 独立旁路，不会错配；汇总或缓存预测时仍须使用联合键。

验证器防回归检查：初次审阅指出 `verify_pair` 对追踪字段的正则仅检查 user，未覆盖 system；根 agent 随后已修正。再次运行负例：将单条 system 改为 `claim_id: 123` 并同步更新逐条 input_sha256，当前验证器正确抛出 `Tracking or annotation field in model prompt`。实际输入另外在本次独立源比对中核验 system/source/builder，均通过。

可复查 `sarol_agent_cross_review.json`；完整校验入口是 `code/ly/verify_route1_data_v2.py`。此次审阅不改变 Sarol 原始缺失证据状态，也不解决 10 条 SciCiteVal 来源标注冲突。
