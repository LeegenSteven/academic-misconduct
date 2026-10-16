#!/usr/bin/env python3
"""Train the SciCiteVal Qwen3.8 LoRA adapter for route1.

This script is deliberately separate from the GGUF M0 runner.  It accepts an
official local Hugging Face Transformers checkpoint and refuses a .gguf path.
Training labels are read from a gold JSONL sidecar or the legacy frozen split
CSV; they are never added to the model input prompts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.route1_qwen38.data_contract import (
    AssistantOnlyCollator, encode_assistant_record, load_gold,
    load_records as load_contract_records,
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
    return load_contract_records(input_path, labels, max_samples=max_samples)


def build_dataset(records: list[dict[str, Any]], tokenizer, max_length: int) -> Dataset:
    return Dataset.from_list([encode_assistant_record(record, tokenizer, max_length) for record in records])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the route1 SciCiteVal Qwen3.8 LoRA adapter")
    parser.add_argument("--model-path", required=True, help="Official local HF Transformers checkpoint; .gguf is rejected")
    parser.add_argument("--inputs", required=True, type=Path, help="SciCiteVal train JSONL without labels")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--gold", type=Path, help="Recommended train.gold.jsonl containing claim_id,label")
    source.add_argument("--split-csv", type=Path, help="Legacy frozen group split CSV containing project_label")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=DEFAULT_LORA["epochs"])
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--input-smoke", "--smoke", dest="input_smoke", action="store_true", help="CPU/tokenizer check of 32 records; NOT a GPU training smoke")
    parser.add_argument("--check-inputs", action="store_true", help="Check every training input, length and collated loss mask; no model loading")
    args = parser.parse_args()
    if args.check_inputs and (args.input_smoke or args.max_samples is not None):
        parser.error("--check-inputs checks the full split and cannot be combined with subset/smoke options")
    return args


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
    gold_path = args.gold or args.split_csv
    for path in (args.inputs, gold_path):
        if not path.exists():
            raise SystemExit(f"Input file does not exist: {path}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    set_seed(DEFAULT_LORA["seed"])
    labels = load_gold(gold_path, split="train")
    max_samples = 32 if args.input_smoke else args.max_samples
    records = load_records(args.inputs, labels, max_samples=max_samples)
    print(f"records={len(records)} labels={dict(Counter(r['label'] for r in records))}")
    print(f"model_path={model_path}")
    print(f"inputs_sha256={sha256_file(args.inputs)} gold_sha256={sha256_file(gold_path)}")

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    train_dataset = build_dataset(records, tokenizer, args.max_length)
    print(f"tokenized_records={len(train_dataset)}")
    if args.input_smoke or args.check_inputs:
        collator = AssistantOnlyCollator(tokenizer)
        supervised_tokens = 0
        for start in range(0, len(train_dataset), 2):
            batch = collator([train_dataset[i] for i in range(start, min(start + 2, len(train_dataset)))])
            supervised_tokens += int((batch["labels"] != -100).sum().item())
        mode = "check_inputs" if args.check_inputs else "input_smoke"
        print(f"{mode}_ok=true records={len(train_dataset)} supervised_tokens={supervised_tokens}; GPU model loading/training NOT performed")
        return

    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training

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
        data_collator=AssistantOnlyCollator(tokenizer),
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
        "gold_path": str(gold_path),
        "gold_sha256": sha256_file(gold_path),
        "train_samples": len(records),
        "label_distribution": dict(Counter(r["label"] for r in records)),
        "lora": DEFAULT_LORA,
        "max_length": args.max_length,
        "target_modules": TARGET_MODULES,
        "supervision": "assistant JSON label and turn end only; supplied masks preserved during padding",
        "enable_thinking": False,
        "truncation_policy": "fail on overlength; do not silently discard evidence or assistant targets",
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
