"""
路线一 Qwen3.8 推理评测脚本
支持 M0（底座）和 Mbio/Mscv（adapter）推理
输出：逐条预测JSONL + 三类P/R/F1 + Macro-F1 + 混淆矩阵
"""
import os, json, argparse, time, sys, hashlib
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.route1_qwen38.data_contract import load_gold, load_records, parse_label, compute_metrics

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


def load_sarol_data(split="dev", max_samples=None, inputs=None, gold_path=None):
    f = inputs or Path(SAROL_INPUT_DIR) / f"model_inputs_{split}_bm25_top10_sentences.jsonl"
    gold_path = gold_path or Path(SAROL_GOLD_DIR) / f"gold_mapping-{split}.csv"
    return load_records(f, load_gold(gold_path, split=split), max_samples=max_samples)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", type=str, default="dev", choices=["train", "dev", "test"], help="train is for GPU-smoke adapter reload checks; official evaluation uses dev/test")
    parser.add_argument("--adapter", type=str, default=None, help="adapter路径，None表示M0底座")
    parser.add_argument("--model-name", "--model_name", dest="model_name", type=str, default="M0", help="模型名称（用于输出文件）")
    parser.add_argument("--model-path", default=MODEL_PATH)
    parser.add_argument("--inputs", type=Path, help="Either dataset's dev/test.inputs.jsonl")
    parser.add_argument("--gold", type=Path, help="Matching dev/test.gold.jsonl or legacy CSV")
    parser.add_argument("--output-dir", type=Path, default=Path(OUTPUT_DIR))
    parser.add_argument("--max-samples", "--max_samples", dest="max_samples", type=int, default=None)
    parser.add_argument("--max-new-tokens", "--max_new_tokens", dest="max_new_tokens", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=4096, help="Full input+generation token budget; overlength fails visibly")
    args = parser.parse_args()

    pred_file = args.output_dir / f"{args.model_name}_{args.split}_predictions.jsonl"
    metric_file = args.output_dir / f"{args.model_name}_{args.split}_metrics.json"
    if pred_file.exists() or metric_file.exists():
        raise SystemExit("Refusing to overwrite earlier attempts; choose a new --output-dir for this run")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"[配置] 模型: {args.model_path}")
    print(f"[配置] Adapter: {args.adapter or 'None (M0底座)'}")
    print(f"[配置] Split: {args.split}")
    print(f"[配置] 输出: {args.output_dir}; enable_thinking=False; retry_policy=none")

    # 加载tokenizer
    print("\n[1/3] 加载tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True, local_files_only=True)
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
        args.model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )

    # 加载adapter
    if args.adapter:
        print(f"  加载adapter: {args.adapter}")
        model = PeftModel.from_pretrained(model, args.adapter)

    model.eval()

    # 加载数据
    print("[3/3] 加载数据...")
    records = load_sarol_data(args.split, max_samples=args.max_samples, inputs=args.inputs, gold_path=args.gold)
    print(f"  样本数: {len(records)}")

    # 推理
    predictions = []
    golds = []

    print(f"\n开始推理（{len(records)}条）...")
    start_time = time.time()

    with open(pred_file, "x", encoding="utf-8") as fp:
        for i, rec in enumerate(records):
            messages = [
                {"role": "system", "content": rec["system_prompt"]},
                {"role": "user", "content": rec["user_prompt"]},
            ]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            inputs = tokenizer(text, add_special_tokens=False, return_tensors="pt", truncation=False).to(model.device)
            input_tokens = inputs["input_ids"].shape[1]
            if input_tokens + args.max_new_tokens > args.max_length:
                raise ValueError(f"claim_id={rec['claim_id']} input={input_tokens}+generation={args.max_new_tokens} exceeds {args.max_length}; no silent truncation")

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=False,
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
                "attempt": 1,
                "retry_count": 0,
                "invalid_reason": "invalid_label_format" if pred_label == "INVALID" else None,
                "input_tokens": input_tokens,
                "output_tokens": int(outputs.shape[1] - input_tokens),
                "generation_at_token_limit": int(outputs.shape[1] - input_tokens) >= args.max_new_tokens,
            }, ensure_ascii=False) + "\n")
            fp.flush()

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
    metrics["enable_thinking"] = False
    metrics["retry_policy"] = "none; all first attempts retained, INVALID scored as errors"
    metrics["retry_count"] = 0
    input_path = args.inputs or Path(SAROL_INPUT_DIR) / f"model_inputs_{args.split}_bm25_top10_sentences.jsonl"
    gold_path = args.gold or Path(SAROL_GOLD_DIR) / f"gold_mapping-{args.split}.csv"
    metrics["inputs_sha256"] = sha256_file(input_path)
    metrics["gold_sha256"] = sha256_file(gold_path)
    metrics["prediction_sha256"] = sha256_file(pred_file)
    metrics["max_length"] = args.max_length
    metrics["truncation_policy"] = "fail on overlength"

    # 保存指标
    with open(metric_file, "x", encoding="utf-8") as fp:
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
