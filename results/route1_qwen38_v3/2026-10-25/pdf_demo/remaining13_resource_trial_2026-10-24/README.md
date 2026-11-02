# 剩余13点：按当前空闲显存试跑

李云本次明确要求先跑。本包移除旧35000 MiB启动门槛，并在原后台加载前设置本进程PyTorch限额：实际空闲减2048 MiB，且不超过整卡95%。这不是显存成功保证，也不覆盖全部外部分配或共享卡性能隔离。

原release、输入、模型、量化、5120/512、reasoning off、greedy、原严格解析均保留；执行记录明确保存资源变体和有效代码哈希。不得把资源变体说成完全未改执行代码。原代码文件不被写入。

先只跑13点classifier。解释阶段须单独启动，使用官方底座、不加载adapter。失败不自动重试、不覆盖旧输出、不推断任何人工验收。

服务器：
python ~/route1_pdf_remaining13_resource_trial_20261024.pyz --launch --stage classifier --gpu 2

默认日志：~/route1_pdf_remaining13_resource_trial_20261024_classifier_run01.run.log
实际逐点日志：~/citation_integrity_member2/incoming/quality_v1_20261009/route1_pdf_remaining13_r2_resource_trial_20261024_run01/classifier/run.log

--launch 使用nohup及独立会话启动，SSH断开后进程继续；返回PID只表示启动，不代表加载或推理完成。
