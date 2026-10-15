#!/usr/bin/env python3
"""Portable entry point for the delivered data, training and evaluation scripts.

No model is downloaded. Test inference runs only with an explicit --stage test.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "results/route1_qwen38_v2/2026-10-15"
TRAINERS = {"sciciteval": ROOT / "code/ly/route1_qwen38_train_sciciteval_v1.py", "sarol": ROOT / "code/cmj/route1_qwen38_train_sarol_v1.py"}
MODEL_NAMES = {"sciciteval": "Mscv", "sarol": "Mbio"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("verify", "check-inputs", "smoke", "train", "dev", "test"))
    parser.add_argument("--dataset", default="both", choices=("both", "sciciteval", "sarol"))
    parser.add_argument("--model-path", type=Path, help="Completed, hash-verified official local HF checkpoint")
    parser.add_argument("--output-root", type=Path, default=Path("runs/route1_qwen38_v2"))
    parser.add_argument("--models", nargs="+", default=["M0"], choices=("M0", "Mbio", "Mscv"))
    parser.add_argument("--mbio-adapter", type=Path)
    parser.add_argument("--mscv-adapter", type=Path)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Freeze on Dev and reuse unchanged for all Test runs")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing any step")
    args = parser.parse_args()
    if args.stage != "verify" and args.model_path is None:
        parser.error("--model-path is required for tokenizer or GPU stages")
    if args.max_length < 1 or args.max_new_tokens < 1 or args.max_new_tokens >= args.max_length:
        parser.error("Need 0 < max-new-tokens < max-length")
    selected = list(TRAINERS) if args.dataset == "both" else [args.dataset]
    output_root = args.output_root.resolve()
    adapters = {
        "Mbio": (args.mbio_adapter or output_root / "train/Mbio/final_adapter").resolve(),
        "Mscv": (args.mscv_adapter or output_root / "train/Mscv/final_adapter").resolve(),
    }
    commands: list[list[str]] = []

    def evaluate(dataset: str, split: str, model_name: str, folder: Path, prefix: str, adapter: Path | None = None) -> list[str]:
        command = [sys.executable, str(ROOT / "code/cmj/route1_qwen38_eval_v1.py"), "--model-path", str(args.model_path.resolve()),
                   "--inputs", str(folder / f"{prefix}.inputs.jsonl"), "--gold", str(folder / f"{prefix}.gold.jsonl"),
                   "--split", split, "--model-name", model_name, "--output-dir", str(output_root / args.stage / dataset / model_name),
                   "--max-length", str(args.max_length), "--max-new-tokens", str(args.max_new_tokens)]
        if adapter is not None:
            command += ["--adapter", str(adapter)]
        return command

    if args.stage == "verify":
        commands.append([sys.executable, str(ROOT / "code/ly/verify_route1_data_v2.py"), "--data-root", str(DATA)])
    elif args.stage in ("check-inputs", "smoke", "train"):
        for dataset in selected:
            prefix = "smoke32" if args.stage == "smoke" else "train"
            folder = DATA / dataset
            name = MODEL_NAMES[dataset] + ("_smoke" if args.stage == "smoke" else "")
            output = output_root / args.stage / name
            command = [sys.executable, str(TRAINERS[dataset]), "--model-path", str(args.model_path.resolve()),
                       "--inputs", str(folder / f"{prefix}.inputs.jsonl"), "--gold", str(folder / f"{prefix}.gold.jsonl"),
                       "--output-dir", str(output), "--max-length", str(args.max_length)]
            if args.stage == "check-inputs":
                command.append("--check-inputs")
            elif args.stage == "smoke":
                command += ["--epochs", "1"]
            commands.append(command)
            if args.stage == "smoke":
                # A separate process reloads the saved adapter and clean base.
                # These are Train-only smoke scores, never Dev/Test results.
                commands.append(evaluate(dataset, "train", name, folder, prefix, output / "final_adapter"))
    else:
        for dataset in selected:
            for model_name in args.models:
                adapter = None if model_name == "M0" else adapters[model_name]
                if adapter is not None and not args.dry_run and not adapter.is_dir():
                    parser.error(f"Missing {model_name} adapter: {adapter}")
                commands.append(evaluate(dataset, args.stage, model_name, DATA / dataset, args.stage, adapter))
    for command in commands:
        print(subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command), flush=True)
        if not args.dry_run:
            subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
