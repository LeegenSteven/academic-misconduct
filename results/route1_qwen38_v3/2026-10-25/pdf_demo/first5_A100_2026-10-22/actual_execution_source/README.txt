PDF首批5点：显存门槛执行修订（2026-10-22）

依据：A100两项固定token缓存预检均通过，12项实际回传文件已核对。
分类器本进程采样峰值23,776 MiB；独立底座解释器23,580 MiB。
此预检不是完整greedy生成保证，实际共享显存仍会变化。

修订：单独执行入口要求空闲>=30,000 MiB，并把PyTorch分配器预算设为当前空闲减2048 MiB。
分配器上限不完全覆盖第三方CUDA分配；不暂停或修改其他用户任务。
原35,000 MiB backend、429项迁移文件、首批范围release及冻结数据均保留。
实际resource_backend.py仅修改原HFBackend初始化的资源门槛/预算；generate方法AST完全一致。
原run_metadata的code_sha256表示原验证合同及参考backend；实际执行backend哈希另外明确记录
在actual_backend_source_sha256与actual_model中，不宣称仍执行原35,000 MiB backend。

不变：官方18分片、Mbio/checkpoint-100分类器、无adapter的独立底座解释器；
NF4/BF16、关闭双量化、reasoning off、greedy、5120/512、同一prompt、解析规则及5点次序。
固定20点分母，两处暂缓与其他15点不执行；不运行Dev/Test，不重训。
解释器不读取分类器结果；任何失败保留首次输出，不重试或改变样本。

步骤（逐条执行）：
1. 上传本pyz并校验外部SHA256。
2. python ~/route1_pdf_first5_resource_v1_20261022.pyz --verify-only
3. python ~/route1_pdf_first5_resource_v1_20261022.pyz --freeze
   CPU核对旧控制包、429项迁移、原release、12项服务器显存证据及token指纹。
   Transformers可导入torch；必须CUDA未初始化，不加载模型。
   创建 /home/admire/route1_pdf_first5_resource_release_20261022/execution_release.json。
   此文件是工程执行补充，不是新的人工范围签名。
4. 检查实时GPU显存，再用外层nohup启动 --run --gpu 2 --operator 李云 --output-dir 全新目录。
   分类器与解释器分别独立进程依次加载；不要直接使用内部 --stage。
5. 两阶段完成后自动调用原assembler。输出20条记录，只有5点有本批模型结果。
   理由仍为未人工复核；reason_for_display为null，正式人工验收仍为0。
   结构、逐字摘录通过不等于语义正确或分类正确；不得写成5点任务已人工验收。

本地检查只验证证据一致性、修订范围、语法和校验拒绝逻辑。
本包正式模型执行尚未开始。不要重复执行，不覆盖已有输出。
