# r2剩余13点冻结控制

仅将李云在本会话的真实范围确认绑定到已通过A100 CPU核验的r2计划。
确认事件时间取自会话元数据，不补造阅读起止时间，不新增标签或语义验收。
本包只提供verify/freeze，不启动GPU，不改写提取的r2代码、输入或旧输出。

python ~/route1_pdf_remaining13_r2_freeze_control_20261024.pyz --verify-only

python ~/route1_pdf_remaining13_r2_freeze_control_20261024.pyz --freeze --root ~/route1_pdf_remaining13_r2_20261024 --bundle ~/route1_pdf_remaining13_cpu_r2_20261024.pyz --cpu-check-dir ~/route1_pdf_remaining13_r2_cpu_check_20261024_attempt1 --source-root ~/route1_pdf_cpu_migration_20261021/source --pymupdf-dir ~/route1_pdf_cpu_deps_20261021 --output-dir ~/route1_pdf_remaining13_r2_release_20261024

成功输出REMAINING13_R2_FROZEN，selected=13、fixed_denominator=20、model_loaded=false。
冻结结果保留7个未选择点；第1/15点不解除暂停，首批5点不重复执行。
