#!/usr/bin/env python3
"""Train the SciCiteVal Qwen3.8 LoRA adapter for route1.

This script is deliberately separate from the GGUF M0 runner.  It accepts an
official local Hugging Face Transformers checkpoint and refuses a .gguf path.
Training labels are read from the frozen group split CSV; they are never added
to the model input prompts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

LABELS = {"ACCURATE", "NOT_ACCURATE", "IRRELEVANT"}
DEFAULT_MAX_LENGTH = 4096
DEFAULT_LORA = {
    "r": 16,
    "alpha": 32,
    "dropout": 0.05,
    "learning_rate": 1e-4,
    "micro_batch": 1,
    "grad_accum": 16,
    "epochs": 1,
    "seed": 42,
}
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_labels(split_csv: Path, split_name: str = "train") -> dict[str, str]:
    with split_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    labels: dict[str, str] = {}
    for row in rows:
        if row.get("split") != split_name:
            continue
        claim_id = str(row["row_id"])
        label = row["project_label"]
        if label not in LABELS:
            raise ValueError(f"Unsupported project_label for {claim_id}: {label!r}")
        if claim_id in labels:
            raise ValueError(f"Duplicate row_id in split CSV: {claim_id}")
        labels[claim_id] = label
    if not labels:
        raise ValueError(f"No rows found for split={split_name!r} in {split_csv}")
    return labels


def load_records(input_path: Path, labels: dict[str, str], max_samples: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    with input_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            data = json.loads(line)
            claim_id = str(data["claim_id"])
            if claim_id not in labels:
                continue
            if claim_id in seen:
                raise ValueError(f"Duplicate claim_id in inputs: {claim_id}")
            if not data.get("system_prompt") or not data.get("user_prompt"):
                raise ValueError(f"Missing prompts at {input_path}:{line_no}")
            seen.add(claim_id)
            records.append({
                "claim_id": claim_id,
                "label": labels[claim_id],
                "system_prompt": data["system_prompt"],
                "user_prompt": data["user_prompt"],
            })
            if max_samples is not None and len(records) >= max_samples:
                break
    missing = set(labels) - seen if max_samples is None else set()
    if missing:
        sample = sorted(missing, key=lambda x: int(x))[:5]
        raise ValueError(f"Missing {len(missing)} split rows in input; examples={sample}")
    if not records:
        raise ValueError("No training records loaded")
    return records


def build_dataset(records: list[dict[str, Any]], tokenizer, max_length: int) -> Dataset:
    input_ids_all: list[list[int]] = []
    labels_all: list[list[int]] = []
    masks_all: list[list[int]] = []
    assistant_marker = tokenizer.encode("<|im_start|>assistant\n", add_special_tokens=False)
    if not assistant_marker:
        raise ValueError("Tokenizer returned an empty assistant marker")

    for record in records:
        messages = [
            {"role": "system", "content": record["system_prompt"]},
            {"role": "user", "content": record["user_prompt"]},
            {"role": "assistant", "content": json.dumps({"label": record["label"]}, ensure_ascii=False)},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        encoded = tokenizer(text, truncation=True, max_length=max_length, return_tensors=None)
        ids = encoded["input_ids"]
        attention = encoded["attention_mask"]
        starts = [
            i for i in range(len(ids) - len(assistant_marker) + 1)
            if ids[i : i + len(assistant_marker)] == assistant_marker
        ]
        if not starts:
            raise ValueError(f"Could not find assistant marker for claim_id={record['claim_id']}")
        assistant_start = starts[-1] + len(assistant_marker)
        target = [-100] * len(ids)
        for i in range(assistant_start, len(ids)):
            target[i] = ids[i]
        if all(value == -100 for value in target):
            raise ValueError(f"Assistant target was truncated for claim_id={record['claim_id']}")
        input_ids_all.append(ids)
        labels_all.append(target)
        masks_all.append(attention)

    return Dataset.from_dict({
        "input_ids": input_ids_all,
        "labels": labels_all,
        "attention_mask": masks_all,
    })


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the route1 SciCiteVal Qwen3.8 LoRA adapter")
    parser.add_argument("--model-path", required=True, help="Official local HF Transformers checkpoint; .gguf is rejected")
    parser.add_argument("--inputs", required=True, type=Path, help="SciCiteVal train JSONL without labels")
    parser.add_argument("--split-csv", required=True, type=Path, help="Frozen group split CSV containing project_label")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=DEFAULT_LORA["epochs"])
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--smoke", action="store_true", help="Load and tokenize 32 records, then stop before model training")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    model_path = Path(args.model_path).expanduser()
    if model_path.suffix.lower() == ".gguf" or model_path.name.lower().endswith(".gguf"):
        raise SystemExit("Refusing GGUF: SciCiteVal adapter training requires the official HF Transformers checkpoint")
    if not model_path.exists() or not model_path.is_dir():
        raise SystemExit(f"HF model directory does not exist: {model_path}")
    if not (model_path / "config.json").exists():
        raise SystemExit(f"Not an HF checkpoint directory (missing config.json): {model_path}")
    for path in (args.inputs, args.split_csv):
        if not path.exists():
            raise SystemExit(f"Input file does not exist: {path}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    set_seed(DEFAULT_LORA["seed"])
    labels = load_labels(args.split_csv)
    max_samples = 32 if args.smoke else args.max_samples
    records = load_records(args.inputs, labels, max_samples=max_samples)
    print(f"records={len(records)} labels={dict(Counter(r['label'] for r in records))}")
    print(f"model_path={model_path}")
    print(f"inputs_sha256={sha256_file(args.inputs)} split_csv_sha256={sha256_file(args.split_csv)}")

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    train_dataset = build_dataset(records, tokenizer, args.max_length)
    print(f"tokenized_records={len(train_dataset)}")
    if args.smoke:
        print("smoke_ok=true (model loading/training skipped)")
        return

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=DEFAULT_LORA["r"],
            lora_alpha=DEFAULT_LORA["alpha"],
            lora_dropout=DEFAULT_LORA["dropout"],
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=TARGET_MODULES,
        ),
    )
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=DEFAULT_LORA["micro_batch"],
        gradient_accumulation_steps=DEFAULT_LORA["grad_accum"],
        learning_rate=DEFAULT_LORA["learning_rate"],
        weight_decay=0.0,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=5,
        save_steps=100,
        save_total_limit=3,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        seed=DEFAULT_LORA["seed"],
        dataloader_pin_memory=False,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    started = time.time()
    result = trainer.train()
    elapsed = time.time() - started
    adapter_dir = args.output_dir / "final_adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    config = {
        "task": "SciCiteVal",
        "status": "trained",
        "base_model_path": str(model_path),
        "base_model_config_sha256": sha256_file(model_path / "config.json"),
        "input_sha256": sha256_file(args.inputs),
        "split_csv_sha256": sha256_file(args.split_csv),
        "train_samples": len(records),
        "label_distribution": dict(Counter(r["label"] for r in records)),
        "lora": DEFAULT_LORA,
        "max_length": args.max_length,
        "target_modules": TARGET_MODULES,
        "supervision": "assistant JSON label only; labels sourced from frozen split CSV",
        "training_time_minutes": round(elapsed / 60, 2),
        "train_result": {k: v for k, v in result.metrics.items() if isinstance(v, (str, int, float, bool))},
    }
    (args.output_dir / "training_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"adapter_dir={adapter_dir}")
    print(f"training_time_minutes={elapsed / 60:.2f}")


if __name__ == "__main__":
    main()
