"""
路线一 Qwen3.8 推理评测脚本
支持 M0（底座）和 Mbio/Mscv（adapter）推理
输出：逐条预测JSONL + 三类P/R/F1 + Macro-F1 + 混淆矩阵
"""
import os, json, argparse, re, time
from pathlib import Path
from collections import defaultdict

import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# ========== 配置 ==========
MODEL_PATH = r"C:\Users\Administrator\Documents\models\Qwen3.8-27B"
SAROL_INPUT_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\results\route1_qwen38_v1\2026-10-13\sarol_bm25_top10_inputs_v1_2026-10-13"
SAROL_GOLD_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\data\quality_v1\sarol"
OUTPUT_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\results\route1_qwen38_v1\2026-10-13"

LABELS = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}


def load_gold_mapping(split="dev"):
    import csv
    gold = {}
    f = os.path.join(SAROL_GOLD_DIR, f"gold_mapping-{split}.csv")
    with open(f, "r", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            gold[int(row["claim_id"])] = row["project_label"]
    return gold


def load_sarol_data(split="dev", max_samples=None):
    f = os.path.join(SAROL_INPUT_DIR, f"model_inputs_{split}_bm25_top10_sentences.jsonl")
    gold = load_gold_mapping(split)
    records = []
    with open(f, "r", encoding="utf-8") as fp:
        for line in fp:
            data = json.loads(line)
            cid = data["claim_id"]
            if cid not in gold:
                continue
            records.append({
                "claim_id": cid,
                "gold": gold[cid],
                "system_prompt": data["system_prompt"],
                "user_prompt": data["user_prompt"],
            })
            if max_samples and len(records) >= max_samples:
                break
    return records


def parse_label(text):
    """从模型输出中解析label"""
    text = text.strip()
    # 尝试解析JSON
    try:
        # 找到第一个{和最后一个}
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            obj = json.loads(text[start:end+1])
            label = obj.get("label", "").strip().upper()
            if label in LABELS:
                return label
    except:
        pass
    # 回退：正则匹配标签
    for label in LABELS:
        if label in text.upper():
            return label
    return "INVALID"


def compute_metrics(predictions, golds):
    """计算三类P/R/F1、Macro-F1、Accuracy、混淆矩阵"""
    n = len(LABELS)
    confusion = [[0]*n for _ in range(n)]
    correct = 0
    invalid = 0

    for pred, gold in zip(predictions, golds):
        if pred not in LABEL2ID:
            invalid += 1
            continue
        pi = LABEL2ID[pred]
        gi = LABEL2ID[gold]
        confusion[gi][pi] += 1
        if pi == gi:
            correct += 1

    total = len(golds)
    accuracy = correct / total if total > 0 else 0

    # 每类P/R/F1
    per_class = {}
    f1_sum = 0
    for i, label in enumerate(LABELS):
        tp = confusion[i][i]
        fp = sum(confusion[j][i] for j in range(n)) - tp
        fn = sum(confusion[i][j] for j in range(n)) - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        per_class[label] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "support": tp+fn}
        f1_sum += f1

    macro_f1 = f1_sum / n

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "invalid_count": invalid,
        "total": total,
        "correct": correct,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", type=str, default="dev", choices=["dev", "test"])
    parser.add_argument("--adapter", type=str, default=None, help="adapter路径，None表示M0底座")
    parser.add_argument("--model_name", type=str, default="M0", help="模型名称（用于输出文件）")
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument("--max_new_tokens", type=int, default=64)
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"[配置] 模型: {MODEL_PATH}")
    print(f"[配置] Adapter: {args.adapter or 'None (M0底座)'}")
    print(f"[配置] Split: {args.split}")
    print(f"[配置] 输出: {OUTPUT_DIR}")

    # 加载tokenizer
    print("\n[1/3] 加载tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 加载模型（4-bit量化推理）
    print("[2/3] 加载模型...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    # 加载adapter
    if args.adapter:
        print(f"  加载adapter: {args.adapter}")
        model = PeftModel.from_pretrained(model, args.adapter)
        model = model.merge_and_unload()

    model.eval()

    # 加载数据
    print("[3/3] 加载数据...")
    records = load_sarol_data(args.split, max_samples=args.max_samples)
    print(f"  样本数: {len(records)}")

    # 推理
    predictions = []
    golds = []
    pred_file = os.path.join(OUTPUT_DIR, f"{args.model_name}_{args.split}_predictions.jsonl")

    print(f"\n开始推理（{len(records)}条）...")
    start_time = time.time()

    with open(pred_file, "w", encoding="utf-8") as fp:
        for i, rec in enumerate(records):
            messages = [
                {"role": "system", "content": rec["system_prompt"]},
                {"role": "user", "content": rec["user_prompt"]},
            ]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=4096).to(model.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=False,
                    temperature=1.0,
                    pad_token_id=tokenizer.pad_token_id,
                )

            generated = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            pred_label = parse_label(generated)

            predictions.append(pred_label)
            golds.append(rec["gold"])

            # 保存逐条预测
            fp.write(json.dumps({
                "claim_id": rec["claim_id"],
                "gold": rec["gold"],
                "pred": pred_label,
                "raw_output": generated,
            }, ensure_ascii=False) + "\n")

            if (i+1) % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  [{i+1}/{len(records)}] {elapsed:.0f}s, 最近预测: {pred_label} (gold: {rec['gold']})")

    elapsed = time.time() - start_time
    print(f"\n推理完成，耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)")

    # 计算指标
    metrics = compute_metrics(predictions, golds)
    metrics["model"] = args.model_name
    metrics["split"] = args.split
    metrics["adapter"] = args.adapter
    metrics["inference_time_seconds"] = round(elapsed, 1)
    metrics["max_new_tokens"] = args.max_new_tokens

    # 保存指标
    metric_file = os.path.join(OUTPUT_DIR, f"{args.model_name}_{args.split}_metrics.json")
    with open(metric_file, "w", encoding="utf-8") as fp:
        json.dump(metrics, fp, indent=2, ensure_ascii=False)

    print(f"\n=== 指标 ===")
    print(f"Accuracy: {metrics['accuracy']} ({metrics['correct']}/{metrics['total']})")
    print(f"Macro-F1: {metrics['macro_f1']}")
    print(f"无效输出: {metrics['invalid_count']}")
    for label in LABELS:
        p = metrics["per_class"][label]
        print(f"  {label}: P={p['precision']}, R={p['recall']}, F1={p['f1']} (support={p['support']})")
    print(f"\n混淆矩阵 (行=gold, 列=pred):")
    print(f"  {'':>15} {'ACCURATE':>10} {'NOT_ACCURATE':>13} {'IRRELEVANT':>12}")
    for i, label in enumerate(LABELS):
        row = metrics["confusion_matrix"][i]
        print(f"  {label:>15} {row[0]:>10} {row[1]:>13} {row[2]:>12}")

    print(f"\n预测文件: {pred_file}")
    print(f"指标文件: {metric_file}")


if __name__ == "__main__":
    main()
