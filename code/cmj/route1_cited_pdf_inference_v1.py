# -*- coding: utf-8 -*-
"""路线一 被引全文证据检索：无 gold 推理（真实引用判定流程原型，在 A100 运行）。

与冻结评测一致的推理设置：同一官方底座、enable_thinking=False、贪心解码、
4-bit NF4、bf16；区别是本脚本不配对 gold、不计算指标——真实边标签待人工盲标，
模型仅给出预测，供后续人工核对引用判定流程是否接通。

用法（A100）：
  python code/cmj/route1_cited_pdf_inference_v1.py \
      --model-path /路径/Qwen3.8-27B \
      --adapter /路径/Mbio_checkpoint-100 \
      --inputs results/cmj/cited_pdf_retrieval_v1_2026-10-18/cited_pdf_demo.inputs.jsonl \
      --output-dir results/cmj/cited_pdf_retrieval_v1_2026-10-18/inference_mbio
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import sys
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "code"))
from shared.route1_qwen38.data_contract import parse_label  # noqa: E402

LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--adapter", default=None, help="adapter 目录；None 表示 M0 底座")
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--max-length", type=int, default=4096)
    ap.add_argument("--operator", default="")
    args = ap.parse_args()

    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit("输出目录非空；请换一个 --output-dir，避免覆盖")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    rows = [json.loads(l) for l in args.inputs.open(encoding="utf-8") if l.strip()]

    print("[1/3] 加载 tokenizer ...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("[2/3] 加载模型（4-bit NF4, bf16）...")
    bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                    bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path, quantization_config=bnb_config, device_map="auto",
        trust_remote_code=True, local_files_only=True)
    if args.adapter:
        print(f"  加载 adapter: {args.adapter}")
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    print(f"[3/3] 逐条推理（{len(rows)} 条，无 gold）...")
    pred_path = args.output_dir / "cited_pdf_demo.predictions.jsonl"
    started = time.time()
    with pred_path.open("w", encoding="utf-8") as out:
        for i, rec in enumerate(rows):
            messages = [
                {"role": "system", "content": rec["system_prompt"]},
                {"role": "user", "content": rec["user_prompt"]},
            ]
            text = tokenizer.apply_chat_template(messages, tokenize=False,
                                                 add_generation_prompt=True, enable_thinking=False)
            enc = tokenizer(text, add_special_tokens=False, return_tensors="pt",
                            truncation=False).to(model.device)
            n_in = enc["input_ids"].shape[1]
            if n_in + args.max_new_tokens > args.max_length:
                raise ValueError(f"{rec['claim_id']} input={n_in} 超过预算，不静默截断")
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=args.max_new_tokens,
                                     do_sample=False, pad_token_id=tokenizer.pad_token_id)
            raw = tokenizer.decode(gen[0][n_in:], skip_special_tokens=True)
            pred = parse_label(raw)
            # 尝试解析完整四字段（模型可能只输出 label；解析失败不影响 label 判定）
            structured = None
            try:
                obj = json.loads(raw.strip().strip("`"))
                if isinstance(obj, dict):
                    structured = {k: obj.get(k) for k in ("label", "evidence_ids", "reason", "confidence")}
            except (ValueError, TypeError):
                structured = None
            out.write(json.dumps({
                "candidate_id": rec["claim_id"],
                "pred": pred,
                "label_valid": pred in LABELS,
                "structured_output": structured,
                "raw_output": raw,
                "input_tokens": int(n_in),
                "input_sha256": rec["input_sha256"],
            }, ensure_ascii=False) + "\n")
            out.flush()
            print(f"  [{i+1}/{len(rows)}] {rec['claim_id']}: pred={pred}", flush=True)

    elapsed = round(time.time() - started, 1)

    # 元数据（GPU / 环境 / 哈希）
    metadata = {
        "purpose": "被引全文证据检索端到端原型：无 gold 推理，标签待人工盲标",
        "operator": args.operator,
        "model_path": args.model_path,
        "adapter": args.adapter,
        "adapter_sha256": file_sha256(Path(args.adapter) / "adapter_model.safetensors") if args.adapter else None,
        "inputs": str(args.inputs),
        "inputs_sha256": file_sha256(args.inputs),
        "predictions": str(pred_path),
        "predictions_sha256": file_sha256(pred_path),
        "enable_thinking": False,
        "do_sample": False,
        "max_new_tokens": args.max_new_tokens,
        "max_length": args.max_length,
        "inference_time_seconds": elapsed,
        "python": platform.python_version(),
        "torch": None,
        "gpu": None,
        "note": "无 gold，不输出指标；人工盲标后另行裁决，再与预测对照",
    }
    try:
        metadata["torch"] = torch.__version__
        if torch.cuda.is_available():
            metadata["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    meta_path = args.output_dir / "cited_pdf_demo.inference_metadata.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    print(f"\n[DONE] 预测: {pred_path}")
    print(f"[DONE] 元数据: {meta_path}（耗时 {elapsed}s）")


if __name__ == "__main__":
    main()
