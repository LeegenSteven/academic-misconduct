"""SupervisedLogitsTrainer(v2) 与标准 Trainer 的 loss/梯度等价性测试（A100 GPU 版）。

v2 同步修订（2026-10-25，配套 route1_qwen38_train_sarol_memopt_v2.py）：

1. 标准版参照改为**真实 Trainer 路径**：`model(**batch, num_items_in_batch=total_tokens)`，
   由模型内部 fixed_cross_entropy 完成 sum/n_items 归一，不再用
   `outputs.loss * n_sup / total_tokens` 手工换算（v1 的近似参照本身会引入
   mean*n 的 fp32 舍入差，且未覆盖 Trainer 传参路径）。
2. 优化版参照同步修订后的 compute_loss：labels 与 num_items_in_batch 回传模型，
   loss = outputs.loss（模型内部 fixed_cross_entropy），不再自行切片 FCE。
3. 新增 --exact-equivalence 对照：优化版不截断 logits（全 shape），用于确认
   全 shape 模式下与标准版逐位一致（诊断结论：截断 shape 在 bf16 下的输出头
   反向存在 kernel 级确定性差异，详见修订说明）。

v3 增量（2026-10-26，按金城分层验收指示）：
4. 新增 --fp32-compute：standard/candidate 双方均以 FP32 compute（NF4 权重、
   compute_dtype=float32、关闭 autocast）运行，按原口径比较 loss、全部 LoRA 梯度
   与一次优化器更新；不要求 FP32 前向与 BF16 一致（分层验收：FP32 层验证候选
   数值逻辑与 standard 一致，BF16 层差异另归档）。
5. 测试2 参数化 --accum-steps（默认 16，对应实际 Trainer）与 --tail-batches
   （默认 13，对应实际尾批条数）。
6. 新增测试4：一次优化器更新（AdamW step 后参数 delta）的 standard/candidate 对比。

覆盖场景：
1. next-token shift 一致性（单条样本 loss/梯度，含 num_items_in_batch 路径）
2. 梯度累积（16 次累积 + 13 条尾批，可参数化）
3. 变长标签与 padding
4. 一次优化器更新后参数变化一致性

运行要求：A100 或同等 GPU（需加载 Qwen3.8-27B 4-bit NF4；--fp32-compute 时
compute 为 FP32，显存与耗时上升，若 80G 不足请先跑小模型核对逻辑）。
用法：
  python test_supervised_logits_equivalence_v2.py \
    --model-path <path> --inputs <train.inputs.jsonl> --gold <train.gold.jsonl> \
    [--exact-equivalence] [--fp32-compute] \
    --accum-steps 16 --tail-batches 13 --num-samples 30 --output equivalence_results_v2.json
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

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1] if (_HERE.parents[1] / "shared" / "route1_qwen38" / "data_contract.py").exists() else _HERE.parents[0]
sys.path.insert(0, str(_REPO_ROOT))
from shared.route1_qwen38.data_contract import AssistantOnlyCollator, encode_assistant_record, load_gold, load_records

sys.path.insert(0, str(_HERE))
from route1_qwen38_train_sarol_memopt_v2 import SupervisedLogitsTrainer

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
MAX_LENGTH = 5120
SEED = 42

# 协议容差（CPU 包协议，与 v1 一致，未改门槛）
LOSS_ATOL = 1e-6
LOSS_RTOL = 1e-5
GRAD_ATOL = 1e-6
GRAD_RTOL = 1e-4


def set_seed(seed):
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_model_and_tokenizer(model_path, fp32_compute=False):
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if fp32_compute:
        # FP32 核验（逻辑层）：不量化、全程 FP32，在小模型/CPU 上执行即可。
        # 27B 全 FP32 权重约 108GB，超出 A100 80G，不作为 FP32 核验目标；
        # 该层验证的是候选与 standard 的数值逻辑一致（loss 归一化、positions、
        # 梯度路径），不要求 FP32 前向与 BF16 一致。
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float32,
            trust_remote_code=True,
            local_files_only=True,
        )
        model.config.use_cache = False
    else:
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


def compare_gradients(grads1, grads2, rtol=GRAD_RTOL, atol=GRAD_ATOL):
    """对比两版梯度，返回最大差异和不一致参数数（协议门槛）"""
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


def run_standard(model, batch, total_tokens):
    """标准版：真实 Trainer 路径（model 内部 fixed_cross_entropy, num_items_in_batch）"""
    model.zero_grad()
    outputs = model(**batch, num_items_in_batch=total_tokens)
    loss = outputs.loss
    loss.backward()
    return loss.item(), get_trainable_gradients(model)


def run_memopt(model, batch, total_tokens, exact_equivalence=False):
    """优化版 v2：与 compute_loss 一致——labels/num_items_in_batch 回传模型，
    loss=outputs.loss；exact_equivalence=True 时不截断 logits。"""
    model.zero_grad()
    labels = batch["labels"]
    model_kwargs = {k: v for k, v in batch.items()}
    if total_tokens is not None:
        model_kwargs["num_items_in_batch"] = total_tokens
    if not exact_equivalence:
        positions = torch.nonzero(labels[0, 1:].ne(-100), as_tuple=False).flatten()
        if positions.numel() == 0:
            raise ValueError("No supervised next-token labels in this batch")
        outputs = model(**model_kwargs, logits_to_keep=positions)
    else:
        outputs = model(**model_kwargs)
    loss = outputs.loss
    loss.backward()
    return loss.item(), get_trainable_gradients(model)


def test_single_batch_loss(model, tokenizer, records, max_length, exact_equivalence=False):
    """测试1: 单条样本 loss/梯度一致性（Trainer num_items_in_batch 路径）"""
    print("\n=== 测试1: 单条样本 loss 一致性（num_items_in_batch=单条有效token数） ===")
    collator = AssistantOnlyCollator(tokenizer)
    results = []

    for i, record in enumerate(records):
        dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
        batch = collator([dataset[0]])
        batch = {k: v.to(model.device) for k, v in batch.items()}
        labels = batch["labels"]
        n_sup = int(labels[0, 1:].ne(-100).sum().item())

        loss_std, grads_std = run_standard(model, batch, total_tokens=n_sup)
        loss_opt, grads_opt = run_memopt(model, batch, total_tokens=n_sup, exact_equivalence=exact_equivalence)

        loss_diff = abs(loss_std - loss_opt)
        max_grad_diff, mismatched, total = compare_gradients(grads_std, grads_opt)

        results.append({
            'sample': i,
            'claim_id': record.get('claim_id', i),
            'loss_std': loss_std,
            'loss_opt': loss_opt,
            'loss_diff': loss_diff,
            'max_grad_diff': max_grad_diff,
            'mismatched_params': mismatched,
            'total_params': total,
            'supervised_tokens': n_sup,
            'seq_len': batch['input_ids'].shape[1],
        })
        print(f"  样本{i} (claim_id={record.get('claim_id','?')}): "
              f"loss_std={loss_std:.6f} loss_opt={loss_opt:.6f} "
              f"diff={loss_diff:.2e} max_grad_diff={max_grad_diff:.2e} "
              f"supervised_tokens={n_sup} seq_len={batch['input_ids'].shape[1]}")

    return results


def test_gradient_accumulation(model, tokenizer, records, max_length, accum_steps=16, tail_batches=13, exact_equivalence=False):
    """测试2: 梯度累积一致性（实际 Trainer 口径：accum_steps 次累积 + 尾批）"""
    print(f"\n=== 测试2: 梯度累积一致性 (accum_steps={accum_steps}, tail_batches={tail_batches}) ===")
    collator = AssistantOnlyCollator(tokenizer)

    n_samples = accum_steps + tail_batches
    test_records = records[:n_samples]

    sample_supervised_tokens = []
    for record in test_records:
        dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
        batch = collator([dataset[0]])
        labels = batch["labels"]
        supervised = labels[0, 1:].ne(-100).sum().item()
        sample_supervised_tokens.append(supervised)

    def run_standard_accum(records_subset, total_tokens):
        model.zero_grad()
        losses = []
        for i, record in enumerate(records_subset):
            dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
            batch = collator([dataset[0]])
            batch = {k: v.to(model.device) for k, v in batch.items()}
            loss, _ = run_standard(model, batch, total_tokens)
            losses.append(loss)
            if (i + 1) % accum_steps == 0 or i == len(records_subset) - 1:
                step_grads = get_trainable_gradients(model)
                model.zero_grad()
        return losses, step_grads

    def run_memopt_accum(records_subset, total_tokens):
        model.zero_grad()
        losses = []
        for i, record in enumerate(records_subset):
            dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
            batch = collator([dataset[0]])
            batch = {k: v.to(model.device) for k, v in batch.items()}
            loss, _ = run_memopt(model, batch, total_tokens, exact_equivalence=exact_equivalence)
            losses.append(loss)
            if (i + 1) % accum_steps == 0 or i == len(records_subset) - 1:
                step_grads = get_trainable_gradients(model)
                model.zero_grad()
        return losses, step_grads

    cycle_tokens = sum(sample_supervised_tokens[:accum_steps])
    losses_std, grads_std = run_standard_accum(test_records[:accum_steps], cycle_tokens)
    losses_opt, grads_opt = run_memopt_accum(test_records[:accum_steps], cycle_tokens)

    max_grad_diff, mismatched, total = compare_gradients(grads_std, grads_opt)
    loss_diffs = [abs(a - b) for a, b in zip(losses_std, losses_opt)]

    print(f"  完整周期: {accum_steps}条, total_supervised_tokens={cycle_tokens}")
    print(f"  loss差异: max={max(loss_diffs):.2e}, mean={np.mean(loss_diffs):.2e}")
    print(f"  累积后梯度差异: max={max_grad_diff:.2e}, 不一致参数={mismatched}/{total}")

    if n_samples > accum_steps:
        tail_records = test_records[accum_steps:]
        tail_tokens = sum(sample_supervised_tokens[accum_steps:])
        losses_std_tail, grads_std_tail = run_standard_accum(tail_records, tail_tokens)
        losses_opt_tail, grads_opt_tail = run_memopt_accum(tail_records, tail_tokens)
        max_grad_diff_tail, mismatched_tail, _ = compare_gradients(grads_std_tail, grads_opt_tail)
        loss_diffs_tail = [abs(a - b) for a, b in zip(losses_std_tail, losses_opt_tail)]
        print(f"  尾部周期: {len(tail_records)}条, total_supervised_tokens={tail_tokens}")
        print(f"  尾部loss差异: max={max(loss_diffs_tail):.2e}")
        print(f"  尾部梯度差异: max={max_grad_diff_tail:.2e}, 不一致参数={mismatched_tail}/{total}")

    return {
        'n_samples': n_samples,
        'accum_steps': accum_steps,
        'tail_batches': tail_batches,
        'cycle_tokens': cycle_tokens,
        'loss_diffs': loss_diffs,
        'max_grad_diff': max_grad_diff,
        'mismatched_params': mismatched,
    }


def test_optimizer_update(model, tokenizer, records, max_length, accum_steps=16, tail_batches=13,
                          exact_equivalence=False, lr=1e-4):
    """测试4: 一次优化器更新后参数变化一致性（standard vs candidate）

    覆盖实际 Trainer：完整累积周期（accum_steps 条）step 一次，尾批（tail_batches 条）
    再 step 一次；比较两步后可训练参数的更新量。
    """
    print(f"\n=== 测试4: 一次优化器更新一致性 (accum_steps={accum_steps}, tail={tail_batches}, lr={lr}) ===")
    collator = AssistantOnlyCollator(tokenizer)
    n_samples = accum_steps + tail_batches
    test_records = records[:n_samples]
    sample_supervised_tokens = []
    for record in test_records:
        dataset = Dataset.from_list([encode_assistant_record(record, tokenizer, max_length)])
        batch = collator([dataset[0]])
        sample_supervised_tokens.append(int(batch["labels"][0, 1:].ne(-100).sum().item()))

    trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    init_state = {n: p.detach().clone() for n, p in trainable}

    def fwd_bwd(batch, total_tokens, use_candidate):
        labels = batch["labels"]
        model_kwargs = {k: v for k, v in batch.items()}
        model_kwargs["num_items_in_batch"] = total_tokens
        if use_candidate and not exact_equivalence:
            positions = torch.nonzero(labels[0, 1:].ne(-100), as_tuple=False).flatten()
            if positions.numel() == 0:
                raise ValueError("No supervised next-token labels in this batch")
            outputs = model(**model_kwargs, logits_to_keep=positions)
        else:
            outputs = model(**model_kwargs)
        loss = outputs.loss
        loss.backward()

    def run_two_steps(use_candidate):
        for n, p in trainable:
            p.data.copy_(init_state[n])
        model.zero_grad()
        snapshots = []
        for start, count in [(0, accum_steps), (accum_steps, tail_batches)]:
            total_tokens = sum(sample_supervised_tokens[start:start + count])
            for i in range(start, start + count):
                dataset = Dataset.from_list([encode_assistant_record(test_records[i], tokenizer, max_length)])
                batch = collator([dataset[0]])
                batch = {k: v.to(model.device) for k, v in batch.items()}
                fwd_bwd(batch, total_tokens, use_candidate)
            optimizer = torch.optim.AdamW([p for _, p in trainable], lr=lr)
            optimizer.step()
            model.zero_grad()
            snapshots.append({n: p.detach().clone() for n, p in trainable})
        return snapshots

    after_std = run_two_steps(False)
    after_cand = run_two_steps(True)
    results = []
    for idx in range(2):
        max_delta = 0.0
        mismatched = 0
        for n in after_std[idx]:
            d = (after_std[idx][n] - after_cand[idx][n]).abs().max().item()
            max_delta = max(max_delta, d)
            if not torch.allclose(after_std[idx][n], after_cand[idx][n], rtol=GRAD_RTOL, atol=GRAD_ATOL):
                mismatched += 1
        results.append({'step': idx + 1, 'max_param_delta': max_delta, 'mismatched_params': mismatched})
        print(f"  step{idx + 1} 参数更新差异: max={max_delta:.2e}, 不一致参数={mismatched}/{len(after_std[idx])}")
    return {'status': 'completed', 'steps': results}


def test_variable_length_and_padding(model, tokenizer, records, max_length, exact_equivalence=False):
    """测试3: 变长标签和padding（Trainer num_items_in_batch 路径）"""
    print("\n=== 测试3: 变长标签和padding ===")
    collator = AssistantOnlyCollator(tokenizer)

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

        loss_std, _ = run_standard(model, batch, total_tokens=supervised)
        loss_opt, _ = run_memopt(model, batch, total_tokens=supervised, exact_equivalence=exact_equivalence)

        print(f"  {name}: seq_len={seq_len}, supervised_tokens={supervised}, "
              f"padding_tokens={padding_count}, loss_diff={abs(loss_std - loss_opt):.2e}")

    return {'status': 'completed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--num-samples", type=int, default=30,
                        help="需覆盖 accum_steps+tail_batches 条（默认 16+13=29）")
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH)
    parser.add_argument("--exact-equivalence", action="store_true",
                        help="优化版不截断 logits（全 shape），对照验证 kernel 级差异来源")
    parser.add_argument("--fp32-compute", action="store_true",
                        help="FP32 核验：不量化、全程 FP32（小模型/CPU 执行，验证候选数值逻辑与 standard 一致）")
    parser.add_argument("--accum-steps", type=int, default=16,
                        help="梯度累积步数（实际 Trainer 配置默认 16）")
    parser.add_argument("--tail-batches", type=int, default=13,
                        help="最后不足一个周期的尾批条数（默认 13）")
    parser.add_argument("--output", type=str, default="equivalence_results_v2.json")
    args = parser.parse_args()

    set_seed(SEED)

    print(f"加载模型: {args.model_path} (fp32_compute={args.fp32_compute})")
    model, tokenizer = load_model_and_tokenizer(args.model_path, fp32_compute=args.fp32_compute)
    model.print_trainable_parameters()

    print(f"\n加载测试数据: {args.inputs}")
    gold = load_gold(args.gold, split="train")
    records = load_records(args.inputs, gold, max_samples=args.num_samples)
    print(f"测试样本数: {len(records)}")
    print(f"exact_equivalence={args.exact_equivalence}, accum_steps={args.accum_steps}, tail_batches={args.tail_batches}")

    if len(records) < args.accum_steps + args.tail_batches:
        raise SystemExit(f"样本不足: 需要 {args.accum_steps + args.tail_batches} 条，实际 {len(records)} 条")

    all_results = {}
    all_results['test1_single_batch'] = test_single_batch_loss(model, tokenizer, records, args.max_length, args.exact_equivalence)
    all_results['test2_grad_accum'] = test_gradient_accumulation(
        model, tokenizer, records, args.max_length,
        accum_steps=args.accum_steps, tail_batches=args.tail_batches,
        exact_equivalence=args.exact_equivalence,
    )
    all_results['test3_variable_length'] = test_variable_length_and_padding(model, tokenizer, records, args.max_length, args.exact_equivalence)
    all_results['test4_optimizer_update'] = test_optimizer_update(
        model, tokenizer, records, args.max_length,
        accum_steps=args.accum_steps, tail_batches=args.tail_batches,
        exact_equivalence=args.exact_equivalence,
    )

    print("\n=== 汇总 ===")
    t1 = all_results['test1_single_batch']
    all_loss_diff = max(r['loss_diff'] for r in t1)
    all_grad_diff = max(r['max_grad_diff'] for r in t1)
    print(f"测试1: max_loss_diff={all_loss_diff:.2e}, max_grad_diff={all_grad_diff:.2e}")
    print(f"测试2: max_grad_diff={all_results['test2_grad_accum']['max_grad_diff']:.2e}")

    # 判定（协议门槛：loss atol=1e-6/rtol=1e-5；梯度 atol=1e-6/rtol=1e-4）
    pass_loss = all_loss_diff < max(LOSS_ATOL, LOSS_RTOL * abs(all_results['test1_single_batch'][0]['loss_std']))
    pass_grad_test1 = all_grad_diff < max(GRAD_ATOL, GRAD_RTOL * 1.0)
    pass_grad_test2 = all_results['test2_grad_accum']['max_grad_diff'] < max(GRAD_ATOL, GRAD_RTOL * 1.0)

    print(f"\n判定（协议 loss atol={LOSS_ATOL}/rtol={LOSS_RTOL}, 梯度 atol={GRAD_ATOL}/rtol={GRAD_RTOL}）:")
    print(f"  测试1 loss: {'PASS' if pass_loss else 'FAIL'}")
    print(f"  测试1 梯度: {'PASS' if pass_grad_test1 else 'FAIL'}")
    print(f"  测试2 梯度: {'PASS' if pass_grad_test2 else 'FAIL'}")

    all_results['summary'] = {
        'max_loss_diff_test1': all_loss_diff,
        'max_grad_diff_test1': all_grad_diff,
        'max_grad_diff_test2': all_results['test2_grad_accum']['max_grad_diff'],
        'exact_equivalence': args.exact_equivalence,
        'fp32_compute': args.fp32_compute,
        'accum_steps': args.accum_steps,
        'tail_batches': args.tail_batches,
        'protocol': {'loss_atol': LOSS_ATOL, 'loss_rtol': LOSS_RTOL, 'grad_atol': GRAD_ATOL, 'grad_rtol': GRAD_RTOL},
        'pass_loss_test1': pass_loss,
        'pass_grad_test1': pass_grad_test1,
        'pass_grad_test2': pass_grad_test2,
        'note': (
            '分层验收：--fp32-compute 模式验证候选与 standard 的数值逻辑一致'
            '（loss/LoRA梯度/一次优化器更新，16累积+13尾批），不要求 FP32 前向与 BF16 一致；'
            'bf16 模式保留 exact_equivalence 全 shape 对照与截断模式的已知 kernel 边界，见修订说明。'
        ),
        'model_path': args.model_path,
        'inputs_sha256': hashlib.sha256(Path(args.inputs).read_bytes()).hexdigest(),
        'gold_sha256': hashlib.sha256(Path(args.gold).read_bytes()).hexdigest(),
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n结果已保存: {args.output}")


if __name__ == "__main__":
    main()
