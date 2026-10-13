"""
路线一 Qwen3.8-27B QLoRA 微调训练脚本（Sarol adapter / Mbio）
配置：4-bit QLoRA, rank16, alpha32, dropout0.05, LR=1e-4, seed42
监督目标：只监督 {"label":"ACCURATE"} 三标签JSON
"""
import os, json, argparse, random, time, hashlib
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
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType

# ========== 配置 ==========
MODEL_PATH = r"C:\Users\Administrator\Documents\models\Qwen3.8-27B"
SAROL_INPUT_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\results\route1_qwen38_v1\2026-10-13\sarol_bm25_top10_inputs_v1_2026-10-13"
SAROL_GOLD_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\data\quality_v1\sarol"
OUTPUT_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\results\route1_qwen38_v1\2026-10-13\mbio_sarol_adapter_v1"

# QLoRA配置
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LEARNING_RATE = 1e-4
SEED = 42
MAX_LENGTH = 4096
MICRO_BATCH = 1
GRAD_ACCUM = 16
NUM_EPOCHS = 1
LOGGING_STEPS = 5
SAVE_STEPS = 100

LABEL2ID = {"ACCURATE": 0, "NOT_ACCURATE": 1, "IRRELEVANT": 2}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_gold_mapping(split="train"):
    """加载gold标签映射"""
    import csv
    gold = {}
    f = os.path.join(SAROL_GOLD_DIR, f"gold_mapping-{split}.csv")
    with open(f, "r", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            gold[int(row["claim_id"])] = row["project_label"]
    return gold


def load_sarol_data(split="train", max_samples=None):
    """加载Sarol训练输入 + gold标签"""
    f = os.path.join(SAROL_INPUT_DIR, f"model_inputs_{split}_bm25_top10_sentences.jsonl")
    gold = load_gold_mapping(split)
    records = []
    with open(f, "r", encoding="utf-8") as fp:
        for line in fp:
            data = json.loads(line)
            cid = data["claim_id"]
            if cid not in gold:
                continue
            label = gold[cid]
            if label not in LABEL2ID:
                continue
            # 构造对话格式
            messages = [
                {"role": "system", "content": data["system_prompt"]},
                {"role": "user", "content": data["user_prompt"]},
                {"role": "assistant", "content": json.dumps({"label": label}, ensure_ascii=False)},
            ]
            records.append({
                "claim_id": cid,
                "label": label,
                "messages": messages,
            })
            if max_samples and len(records) >= max_samples:
                break
    return records


def build_dataset(records, tokenizer):
    """将对话格式转为tokenized训练样本，只监督assistant回复部分"""
    all_input_ids = []
    all_labels = []
    all_attention_mask = []

    for rec in records:
        # 用tokenizer的apply_chat_template
        text = tokenizer.apply_chat_template(
            rec["messages"], tokenize=False, add_generation_prompt=False
        )
        enc = tokenizer(text, truncation=True, max_length=MAX_LENGTH, return_tensors=None)
        input_ids = enc["input_ids"]
        attention_mask = enc["attention_mask"]

        # 找到assistant回复的起始位置（只监督这部分）
        # Qwen3的chat template中，assistant回复前有特定的标记
        # 简单方法：找到最后一个assistant标记的位置
        assistant_start = 0
        # 搜索assistant token的位置
        assistant_marker = tokenizer.encode("<|im_start|>assistant\n", add_special_tokens=False)
        for i in range(len(input_ids) - len(assistant_marker) + 1):
            if input_ids[i:i+len(assistant_marker)] == assistant_marker:
                assistant_start = i + len(assistant_marker)

        labels = [-100] * len(input_ids)
        for i in range(assistant_start, len(input_ids)):
            labels[i] = input_ids[i]

        all_input_ids.append(input_ids)
        all_labels.append(labels)
        all_attention_mask.append(attention_mask)

    return Dataset.from_dict({
        "input_ids": all_input_ids,
        "labels": all_labels,
        "attention_mask": all_attention_mask,
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="冒烟测试：只用32条")
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS)
    parser.add_argument("--output_dir", type=str, default=OUTPUT_DIR)
    args = parser.parse_args()

    set_seed(SEED)
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"[配置] 模型: {MODEL_PATH}")
    print(f"[配置] QLoRA: r={LORA_R}, alpha={LORA_ALPHA}, dropout={LORA_DROPOUT}")
    print(f"[配置] LR={LEARNING_RATE}, batch={MICRO_BATCH}, grad_accum={GRAD_ACCUM}, epochs={args.epochs}")
    print(f"[配置] max_length={MAX_LENGTH}, seed={SEED}")
    print(f"[配置] 输出: {args.output_dir}")
    if args.smoke:
        print("[配置] 冒烟测试模式：32条")

    # 加载tokenizer
    print("\n[1/4] 加载tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 4-bit量化配置
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # 加载模型
    print("[2/4] 加载模型（4-bit量化）...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # 配置QLoRA
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 加载数据
    print("[3/4] 加载训练数据...")
    max_samples = 32 if args.smoke else None
    train_records = load_sarol_data("train", max_samples=max_samples)
    print(f"  训练样本: {len(train_records)}")
    label_counts = {}
    for r in train_records:
        label_counts[r["label"]] = label_counts.get(r["label"], 0) + 1
    print(f"  标签分布: {label_counts}")

    train_dataset = build_dataset(train_records, tokenizer)
    print(f"  tokenized样本: {len(train_dataset)}")

    # 训练参数
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=MICRO_BATCH,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        weight_decay=0.0,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=LOGGING_STEPS,
        save_steps=SAVE_STEPS,
        save_total_limit=3,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        seed=SEED,
        dataloader_pin_memory=False,
    )

    # 数据collator
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    # 训练
    print("[4/4] 开始训练...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )

    start_time = time.time()
    trainer.train()
    elapsed = time.time() - start_time
    print(f"\n训练完成，耗时: {elapsed/60:.1f} 分钟")

    # 保存adapter
    adapter_path = os.path.join(args.output_dir, "final_adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"Adapter已保存: {adapter_path}")

    # 保存训练配置
    config = {
        "model_path": MODEL_PATH,
        "model_revision": "main",
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "learning_rate": LEARNING_RATE,
        "micro_batch": MICRO_BATCH,
        "grad_accum": GRAD_ACCUM,
        "epochs": args.epochs,
        "max_length": MAX_LENGTH,
        "seed": SEED,
        "train_samples": len(train_records),
        "label_distribution": label_counts,
        "training_time_minutes": round(elapsed / 60, 1),
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "supervision": "only assistant label JSON {\"label\":\"...\"}",
    }
    with open(os.path.join(args.output_dir, "training_config.json"), "w", encoding="utf-8") as fp:
        json.dump(config, fp, indent=2, ensure_ascii=False)
    print("训练配置已保存")


if __name__ == "__main__":
    main()
