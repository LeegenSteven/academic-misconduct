"""
路线一 Qwen3.8-27B QLoRA 微调训练脚本（Sarol adapter / Mbio）
配置：4-bit QLoRA, rank16, alpha32, dropout0.05, LR=1e-4, seed42
监督目标：只监督 {"label":"ACCURATE"} 三标签JSON
"""
import os, json, argparse, random, time, hashlib, sys
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.route1_qwen38.data_contract import AssistantOnlyCollator, encode_assistant_record, load_gold, load_records

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


def load_sarol_data(split="train", max_samples=None, inputs=None, gold_path=None):
    """加载Sarol训练输入 + gold标签"""
    f = inputs or Path(SAROL_INPUT_DIR) / f"model_inputs_{split}_bm25_top10_sentences.jsonl"
    gold_path = gold_path or Path(SAROL_GOLD_DIR) / f"gold_mapping-{split}.csv"
    return load_records(f, load_gold(gold_path, split=split), max_samples=max_samples)


def build_dataset(records, tokenizer, max_length=MAX_LENGTH):
    """将对话格式转为tokenized训练样本，只监督assistant回复部分"""
    return Dataset.from_list([encode_assistant_record(record, tokenizer, max_length) for record in records])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="GPU训练32条；并非仅分词检查")
    parser.add_argument("--input-smoke", action="store_true", help="仅分词和CPU batch检查，不加载模型")
    parser.add_argument("--check-inputs", action="store_true", help="检查全量输入的分词、长度与实际batch监督mask，不加载模型")
    parser.add_argument("--model-path", default=MODEL_PATH)
    parser.add_argument("--inputs", type=Path, help="Recommended train.inputs.jsonl; old path remains the default")
    parser.add_argument("--gold", type=Path, help="Recommended train.gold.jsonl or legacy gold CSV")
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS)
    parser.add_argument("--output-dir", "--output_dir", dest="output_dir", type=str, default=OUTPUT_DIR)
    args = parser.parse_args()
    if args.check_inputs and (args.smoke or args.input_smoke or args.max_samples is not None):
        parser.error("--check-inputs checks the full split and cannot be combined with subset/smoke options")

    set_seed(SEED)
    os.makedirs(args.output_dir, exist_ok=True)

    if str(args.model_path).lower().endswith(".gguf"):
        raise SystemExit("Training requires the official HF checkpoint, not GGUF")
    print(f"[配置] 模型: {args.model_path}")
    print(f"[配置] QLoRA: r={LORA_R}, alpha={LORA_ALPHA}, dropout={LORA_DROPOUT}")
    print(f"[配置] LR={LEARNING_RATE}, batch={MICRO_BATCH}, grad_accum={GRAD_ACCUM}, epochs={args.epochs}")
    print(f"[配置] max_length={args.max_length}, seed={SEED}, enable_thinking=False")
    print(f"[配置] 输出: {args.output_dir}")
    if args.smoke:
        print("[配置] 冒烟测试模式：32条")

    # 加载tokenizer
    print("\n[1/4] 加载tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    max_samples = 32 if args.smoke or args.input_smoke else args.max_samples
    train_records = load_sarol_data("train", max_samples=max_samples, inputs=args.inputs, gold_path=args.gold)
    label_counts = {}
    for record in train_records:
        label_counts[record["label"]] = label_counts.get(record["label"], 0) + 1
    train_dataset = build_dataset(train_records, tokenizer, args.max_length)
    print(f"  tokenized样本: {len(train_dataset)}, 标签分布: {label_counts}")
    if args.input_smoke or args.check_inputs:
        collator = AssistantOnlyCollator(tokenizer)
        supervised_tokens = 0
        for start in range(0, len(train_dataset), 2):
            batch = collator([train_dataset[i] for i in range(start, min(start + 2, len(train_dataset)))])
            supervised_tokens += int((batch["labels"] != -100).sum().item())
        mode = "check_inputs" if args.check_inputs else "input_smoke"
        print(f"{mode}_ok=true records={len(train_dataset)} supervised_tokens={supervised_tokens}; GPU model loading/training NOT performed")
        return

    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType

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
        args.model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )
    model.config.use_cache = False
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
    print(f"  训练样本: {len(train_records)}")
    print(f"  标签分布: {label_counts}")

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
    data_collator = AssistantOnlyCollator(tokenizer)

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
        "model_path": args.model_path,
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "learning_rate": LEARNING_RATE,
        "micro_batch": MICRO_BATCH,
        "grad_accum": GRAD_ACCUM,
        "epochs": args.epochs,
        "max_length": args.max_length,
        "seed": SEED,
        "train_samples": len(train_records),
        "label_distribution": label_counts,
        "training_time_minutes": round(elapsed / 60, 1),
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "supervision": "only assistant label JSON {\"label\":\"...\"}",
        "enable_thinking": False,
        "truncation_policy": "fail on overlength; no silent truncation",
        "input_path": str(args.inputs or Path(SAROL_INPUT_DIR) / "model_inputs_train_bm25_top10_sentences.jsonl"),
        "gold_path": str(args.gold or Path(SAROL_GOLD_DIR) / "gold_mapping-train.csv"),
    }
    for key in ("input", "gold"):
        path = Path(config[f"{key}_path"])
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        config[f"{key}_sha256"] = digest.hexdigest()
    with open(os.path.join(args.output_dir, "training_config.json"), "w", encoding="utf-8") as fp:
        json.dump(config, fp, indent=2, ensure_ascii=False)
    print("训练配置已保存")


if __name__ == "__main__":
    main()
