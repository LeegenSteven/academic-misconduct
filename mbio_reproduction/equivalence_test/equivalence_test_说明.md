# equivalence_test 说明（loss 归一化等价性）

## 1. 结论（李云 2026-10-20 CPU 实测回传）

李云《发给陈明进_CPU等价性修复实测_20261020》结论：**通过**。

| 场景 | 结果 |
|---|---|
| 五个正向场景（loss 归一化修复候选） | 梯度最大差 0、更新后参数最大差 0 |
| loss 最大绝对差 | 9.5367431640625e-7（atol=1e-6 / rtol=1e-5，未放宽） |
| 负例对照（旧归一化版本） | 正确拒绝：scaled loss 最大差约 0.163931、梯度约 1.69e-4、参数约 3.38e-4 |

A100 环境：Python 3.13.12、torch 2.11.0+cu130、transformers 5.8.0、PEFT 0.21.2、accelerate 1.14.0、datasets 5.0.0。

## 2. 测试脚本（本归档 code/）

- `test_supervised_logits_equivalence.py`（SHA256 AE0F122C1DB46ABCC97060799DA298849814888A93646ED756529D8759481F10）：
  - 测试1：单条样本 loss/梯度（标准版 vs 优化版）
  - 测试2：梯度累积（含最后不足一个周期，正确模拟 `num_items_in_batch`）
  - 测试3：变长标签与 padding
  - 内置判定阈值：loss < 1e-5、grad < 1e-4
- `route1_qwen38_train_sarol_memopt_v1.py`（SHA256 9A47A2DA…）：修复后训练脚本，`compute_loss` 中 `num_items_in_batch` 非 None 时 `sum / num_items_in_batch`、None 时 `mean`。

## 3. 两套容差口径（重要，勿混用）

| 来源 | 容差 |
|---|---|
| 李云 CPU 包协议 | loss atol=1e-6 / rtol=1e-5；梯度与参数 atol=1e-6 / rtol=1e-4 |
| 测试脚本内置阈值 | threshold_loss=1e-5、threshold_grad=1e-4 |

GPU 请求包（27B/NF4）已按李云 CPU 包协议口径显式写明，避免与脚本内置阈值混淆。

## 4. 边界

CPU 通过 ≠ 27B/NF4 逐位等价；不把历史 checkpoint 写成已自动修复。27B/NF4 GPU 等价性验证与 checkpoint 保存/重载验证待 A100 执行（见 audit.md §5）。
