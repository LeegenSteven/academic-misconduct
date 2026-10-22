"""Portable CPU-only check of the PDF20 draft inputs against actual base tokenizer.

No model weights, training or inference; passing does not release draft scopes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

HASHES = {
    "tokenizer.json": "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3",
    "tokenizer_config.json": "b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27",
    "config.json": "191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab",
    "chat_template.jinja": "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-path", type=Path, required=True, help="Official base directory, only tokenizer/config files read")
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--budget-report", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--tokenizer-deps", type=Path)
    args = p.parse_args()
    require(not args.output.exists(), "Output already exists")
    os.environ.update(CUDA_VISIBLE_DEVICES="", USE_TORCH="0", USE_TF="0", HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    if args.tokenizer_deps:
        sys.path.insert(0, str(args.tokenizer_deps.resolve()))
    import transformers
    from transformers import AutoTokenizer
    require(transformers.__version__ == "5.8.0", "Require the frozen transformers 5.8.0 tokenizer implementation")
    for name, expected in HASHES.items():
        require(sha(args.model_path / name) == expected, f"Base tokenizer/config hash mismatch: {name}")
    inputs = [json.loads(line) for line in args.inputs.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    budgets = json.loads(args.budget_report.read_text(encoding="utf-8"))["rows"]
    expected = {r["case_id"]: r for r in budgets}
    require(len(inputs) == len(budgets) == len(expected) == 20, "Must retain all 20 points")
    require(len({r["claim_id"] for r in inputs}) == 20 and {r["claim_id"] for r in inputs} == set(expected), "Duplicate or missing input ID")
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    results = []
    for record in inputs:
        payload = {k: record[k] for k in ("system_prompt", "user_prompt")}
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        require(digest == record["input_sha256"], "Model-visible payload hash mismatch")
        text = tokenizer.apply_chat_template([{"role": "system", "content": payload["system_prompt"]},
                                             {"role": "user", "content": payload["user_prompt"]}],
                                            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        ids = tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"]
        fingerprint = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode("utf-8")).hexdigest()
        budget = expected[record["claim_id"]]
        require(len(ids) == budget["input_tokens"], "Token count differs from preparation")
        require(fingerprint == budget["input_ids_sha256"] == record["expected_input_ids_sha256"], "Actual token IDs differ")
        require(len(ids) + 512 <= 5120, "Context overflow; no truncation permitted")
        results.append({"case_id": record["claim_id"], "input_tokens": len(ids), "input_ids_sha256": fingerprint,
                        "required_total": len(ids) + 512, "scope_hold": record.get("scope_hold")})
    report = {"status": "passed_CPU_token_identity_only", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "checker_sha256": sha(Path(__file__)), "inputs_sha256": sha(args.inputs), "budget_report_sha256": sha(args.budget_report),
              "official_tokenizer_files_sha256": HASHES, "transformers": transformers.__version__, "rows": results,
              "points": 20, "scope_holds": sum(bool(r["scope_hold"]) for r in results),
              "model_loaded": False, "gpu_used": False, "formal_input_release": False,
              "note": "CPU parity is not scope signoff, a model result, semantic acceptance, or two-person adjudication."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CPU_TOKEN_IDENTITY_PASS records=20 scope_holds={report['scope_holds']} model_loaded=false GPU_used=false")


if __name__ == "__main__":
    main()
