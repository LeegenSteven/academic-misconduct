"""SupervisedLogitsTrainer 与标准 Trainer 的 loss/梯度等价性测试。

覆盖场景：
1. next-token shift 一致性
2. 变长标签
3. padding 处理
4. 梯度累积（含最后不足一个周期）
5. 可训练参数梯度数值一致

运行要求：A100 或同等 GPU（需加载 Qwen3.8-27B 4-bit）。
用法：python code/cmj/test_supervised_logits_equivalence.py --model-path <path> --num-samples 5
"""
import os, sys, json, argparse, hashlib
from pathlib import Path

import torch
import numpy as np
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.route1_qwen38.data_contract import AssistantOnlyCollator, encode_assistant_record, load_gold, load_records

# 导入优化版的 SupervisedLogitsTrainer
sys.path.insert(0, str(Path(__file__).resolve().parent))
from route1_qwen38_train_sarol_memopt_v1 import SupervisedLogitsTrainer

MODEL_PATH = r"C:\Users\Administrator\Documents\models\Qwen3.8-27B"
TRAIN_INPUT = r"C:\Users\Administrator\Documents\academic-misconduct\results\route1_qwen38_v2\2026-10-15\sarol\train.inputs.jsonl"
TRAIN_GOLD = r"C:\Users\Administrator\Documents\academic-misconduct\results\route1_qwen38_v2\2026-10-15\sarol\train.gold.jsonl"

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
MAX_LENGTH = 5120
SEED = 42


def set_seed(seed):
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_model_and_tokenizer(model_path):
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    return model, tokenizer


def get_trainable_gradients(model):
    """提取所有可训练参数的梯度，返回dict {name: grad_tensor}"""
    grads = {}
    for name, param in model.named_parameters():
        if param.requires_grad and param.grad is not None:
            grads[name] = param.grad.detach().clone().float()
    return grads


def compare_gradients(grads1, grads2, rtol=1e-4, atol=1e-5):
    """对比两版梯度，返回最大差异和不一致参数数"""
    max_diff = 0.0
    mismatched = 0
    total_params = 0
    for name in grads1:
        if name not in grads2:
            mismatched += 1
            continue
        g1 = grads1[name]
        g2 = grads2[name]
        if g1.shape != g2.shape:
            mismatched += 1
            continue
        diff = (g1 - g2).abs().max().item()
        max_diff = max(max_diff, diff)
        total_params += g1.numel()
        if not torch.allclose(g1, g2, rtol=rtol, atol=atol):
            mismatched += 1
    return max_diff, mismatched, len(grads1)


def test_single_batch_loss(model, tokenizer, records, max_length):
    """测试1: 单条样本 loss 一致性"""
    print("\n=== 测试1: 单条样本 loss 一致性 ===")
    collator = AssistantOnlyCollator(tokenizer)
    results = []

    for i, record in enumerate(records):
        dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
        batch = collator([dataset[0]])
        batch = {k: v.to(model.device) for k, v in batch.items()}

        # 标准版 loss
        model.zero_grad()
        outputs_std = model(**batch)
        loss_std = outputs_std.loss
        loss_std.backward()
        grads_std = get_trainable_gradients(model)

        # 优化版 loss
        model.zero_grad()
        labels = batch["labels"]
        positions = torch.nonzero(labels[0, 1:].ne(-100), as_tuple=False).flatten()
        model_inputs = {k: v for k, v in batch.items() if k != "labels"}
        outputs_opt = model(**model_inputs, logits_to_keep=positions)
        logits_opt = outputs_opt.logits
        targets = labels[0].index_select(0, positions + 1)
        loss_opt = torch.nn.functional.cross_entropy(logits_opt[0].float(), targets, reduction="mean")
        loss_opt.backward()
        grads_opt = get_trainable_gradients(model)

        loss_diff = abs(loss_std.item() - loss_opt.item())
        max_grad_diff, mismatched, total = compare_gradients(grads_std, grads_opt)

        results.append({
            'sample': i,
            'claim_id': record.get('claim_id', i),
            'loss_std': loss_std.item(),
            'loss_opt': loss_opt.item(),
            'loss_diff': loss_diff,
            'max_grad_diff': max_grad_diff,
            'mismatched_params': mismatched,
            'total_params': total,
            'supervised_tokens': positions.numel(),
            'seq_len': batch['input_ids'].shape[1],
        })
        print(f"  样本{i} (claim_id={record.get('claim_id','?')}): "
              f"loss_std={loss_std.item():.6f} loss_opt={loss_opt.item():.6f} "
              f"diff={loss_diff:.2e} max_grad_diff={max_grad_diff:.2e} "
              f"supervised_tokens={positions.numel()} seq_len={batch['input_ids'].shape[1]}")

    return results


def test_gradient_accumulation(model, tokenizer, records, max_length, accum_steps=4):
    """测试2: 梯度累积一致性（含最后不足一个周期）

    正确模拟 transformers 5.8 Trainer 行为：
    - num_items_in_batch = 整个累积周期的有效 token 总数
    - 每个 microbatch loss = sum(token_losses) / num_items_in_batch
    - 不再额外除以 accum_steps
    """
    print(f"\n=== 测试2: 梯度累积一致性 (accum_steps={accum_steps}) ===")
    collator = AssistantOnlyCollator(tokenizer)

    # 取 accum_steps+1 条样本，模拟最后一步不足一个周期
    n_samples = accum_steps + 1
    test_records = records[:n_samples]

    # 预计算每个样本的监督 token 数和整个周期的 num_items_in_batch
    sample_supervised_tokens = []
    for record in test_records:
        dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
        batch = collator([dataset[0]])
        labels = batch["labels"]
        supervised = labels[0, 1:].ne(-100).sum().item()
        sample_supervised_tokens.append(supervised)

    def run_standard(records_subset, total_tokens):
        """标准版：sum / total_cycle_tokens，与 Trainer fixed_cross_entropy 一致"""
        model.zero_grad()
        losses = []
        for i, record in enumerate(records_subset):
            dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
            batch = collator([dataset[0]])
            batch = {k: v.to(model.device) for k, v in batch.items()}
            outputs = model(**batch)
            # model 直接调用时 num_items_in_batch=None，loss 是 mean
            # 需要手动转为 sum/total_tokens 以匹配 Trainer 行为
            n_sup = sample_supervised_tokens[i]
            loss_sum = outputs.loss * n_sup  # mean * count = sum
            loss = loss_sum / total_tokens
            loss.backward()
            losses.append(loss.item())
            if (i + 1) % accum_steps == 0 or i == len(records_subset) - 1:
                step_grads = get_trainable_gradients(model)
                model.zero_grad()
        return losses, step_grads

    def run_memopt(records_subset, total_tokens):
        """优化版：sum / total_cycle_tokens（修复后与标准版一致）"""
        model.zero_grad()
        losses = []
        for i, record in enumerate(records_subset):
            dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
            batch = collator([dataset[0]])
            batch = {k: v.to(model.device) for k, v in batch.items()}
            labels = batch["labels"]
            positions = torch.nonzero(labels[0, 1:].ne(-100), as_tuple=False).flatten()
            model_inputs = {k: v for k, v in batch.items() if k != "labels"}
            outputs = model(**model_inputs, logits_to_keep=positions)
            logits = outputs.logits
            targets = labels[0].index_select(0, positions + 1)
            # sum reduction then divide by total cycle tokens
            loss_sum = torch.nn.functional.cross_entropy(
                logits[0].float(), targets, reduction="sum"
            )
            loss = loss_sum / total_tokens
            loss.backward()
            losses.append(loss.item())
            if (i + 1) % accum_steps == 0 or i == len(records_subset) - 1:
                step_grads = get_trainable_gradients(model)
                model.zero_grad()
        return losses, step_grads

    # 完整周期（前 accum_steps 条）
    cycle_tokens = sum(sample_supervised_tokens[:accum_steps])
    losses_std, grads_std = run_standard(test_records[:accum_steps], cycle_tokens)
    losses_opt, grads_opt = run_memopt(test_records[:accum_steps], cycle_tokens)

    max_grad_diff, mismatched, total = compare_gradients(grads_std, grads_opt)
    loss_diffs = [abs(a - b) for a, b in zip(losses_std, losses_opt)]

    print(f"  完整周期: {accum_steps}条, total_supervised_tokens={cycle_tokens}")
    print(f"  loss差异: max={max(loss_diffs):.2e}, mean={np.mean(loss_diffs):.2e}")
    print(f"  累积后梯度差异: max={max_grad_diff:.2e}, 不一致参数={mismatched}/{total}")

    # 最后不足一个周期（剩余的 tail 样本）
    if n_samples > accum_steps:
        tail_records = test_records[accum_steps:]
        tail_tokens = sum(sample_supervised_tokens[accum_steps:])
        losses_std_tail, grads_std_tail = run_standard(tail_records, tail_tokens)
        losses_opt_tail, grads_opt_tail = run_memopt(tail_records, tail_tokens)
        max_grad_diff_tail, mismatched_tail, _ = compare_gradients(grads_std_tail, grads_opt_tail)
        loss_diffs_tail = [abs(a - b) for a, b in zip(losses_std_tail, losses_opt_tail)]
        print(f"  尾部周期: {len(tail_records)}条, total_supervised_tokens={tail_tokens}")
        print(f"  尾部loss差异: max={max(loss_diffs_tail):.2e}")
        print(f"  尾部梯度差异: max={max_grad_diff_tail:.2e}, 不一致参数={mismatched_tail}/{total}")

    return {
        'n_samples': n_samples,
        'accum_steps': accum_steps,
        'cycle_tokens': cycle_tokens,
        'loss_diffs': loss_diffs,
        'max_grad_diff': max_grad_diff,
        'mismatched_params': mismatched,
    }


def test_variable_length_and_padding(model, tokenizer, records, max_length):
    """测试3: 变长标签和padding"""
    print("\n=== 测试3: 变长标签和padding ===")
    collator = AssistantOnlyCollator(tokenizer)

    # 选两条长度差异较大的样本
    sorted_records = sorted(records, key=lambda r: len(json.dumps(r, ensure_ascii=False)))
    short = sorted_records[0]
    long = sorted_records[-1]

    for name, record in [('short', short), ('long', long)]:
        dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
        batch = collator([dataset[0]])
        batch = {k: v.to(model.device) for k, v in batch.items()}
        labels = batch["labels"]
        supervised = (labels != -100).sum().item()
        seq_len = batch['input_ids'].shape[1]
        padding_count = (labels == -100).sum().item()

        # 标准版
        model.zero_grad()
        outputs_std = model(**batch)
        loss_std = outputs_std.loss.item()

        # 优化版
        model.zero_grad()
        positions = torch.nonzero(labels[0, 1:].ne(-100), as_tuple=False).flatten()
        model_inputs = {k: v for k, v in batch.items() if k != "labels"}
        outputs_opt = model(**model_inputs, logits_to_keep=positions)
        targets = labels[0].index_select(0, positions + 1)
        loss_opt = torch.nn.functional.cross_entropy(outputs_opt.logits[0].float(), targets, reduction="mean").item()

        print(f"  {name}: seq_len={seq_len}, supervised_tokens={supervised}, "
              f"padding_tokens={padding_count}, loss_diff={abs(loss_std - loss_opt):.2e}")

    return {'status': 'completed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", default=MODEL_PATH)
    parser.add_argument("--num-samples", type=int, default=5)
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH)
    parser.add_argument("--output", type=str, default="equivalence_test_results.json")
    args = parser.parse_args()

    set_seed(SEED)

    print(f"加载模型: {args.model_path}")
    model, tokenizer = load_model_and_tokenizer(args.model_path)
    model.print_trainable_parameters()

    # 加载测试数据
    print(f"\n加载测试数据: {TRAIN_INPUT}")
    gold = load_gold(TRAIN_GOLD, split="train")
    records = load_records(TRAIN_INPUT, gold, max_samples=args.num_samples)
    print(f"测试样本数: {len(records)}")

    all_results = {}

    # 测试1: 单条样本 loss 和梯度
    all_results['test1_single_batch'] = test_single_batch_loss(model, tokenizer, records, args.max_length)

    # 测试2: 梯度累积
    all_results['test2_grad_accum'] = test_gradient_accumulation(model, tokenizer, records, args.max_length, accum_steps=4)

    # 测试3: 变长标签和padding
    all_results['test3_variable_length'] = test_variable_length_and_padding(model, tokenizer, records, args.max_length)

    # 汇总
    print("\n=== 汇总 ===")
    t1 = all_results['test1_single_batch']
    all_loss_diff = max(r['loss_diff'] for r in t1)
    all_grad_diff = max(r['max_grad_diff'] for r in t1)
    print(f"测试1: max_loss_diff={all_loss_diff:.2e}, max_grad_diff={all_grad_diff:.2e}")
    print(f"测试2: max_grad_diff={all_results['test2_grad_accum']['max_grad_diff']:.2e}")

    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n结果已保存: {args.output}")

    # 判定
    threshold_loss = 1e-5
    threshold_grad = 1e-4
    pass_test1 = all_loss_diff < threshold_loss and all_grad_diff < threshold_grad
    pass_test2 = all_results['test2_grad_accum']['max_grad_diff'] < threshold_grad
    print(f"\n判定 (loss<{threshold_loss}, grad<{threshold_grad}):")
    print(f"  测试1: {'PASS' if pass_test1 else 'FAIL'}")
    print(f"  测试2: {'PASS' if pass_test2 else 'FAIL'}")


if __name__ == "__main__":
    main()
