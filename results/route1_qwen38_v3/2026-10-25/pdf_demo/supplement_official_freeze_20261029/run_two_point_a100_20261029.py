"""Run one frozen two-point model stage on exactly one A100.

This runner is separate from the historical 13-point runtime. It writes a new
stage directory and never overwrites prepared inputs or historical results.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[4] / "code" / "ly"
sys.path.insert(0, str(CODE))

import route1_pdf_pipeline_v3 as contract
from route1_pdf_hf_backend_v3 import HFBackend


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def strict_json(raw):
    return json.loads(raw.strip())


def parse_classifier(raw):
    try:
        obj = strict_json(raw)
        if obj == {"failure_status": "insufficient_evidence"}:
            return {"status": "insufficient_evidence", "label": None}
        if obj.get("label") not in contract.LABELS or "failure_status" in obj:
            raise ValueError("invalid classifier object")
        return {"status": "valid_label", "label": obj["label"],
                "extra_fields_ignored": sorted(set(obj) - {"label"})}
    except Exception as error:
        return {"status": "invalid_classifier_output", "label": None, "error": str(error)}


def parse_explanation(raw, candidates):
    try:
        return contract.parse_explanation(raw, candidates)
    except Exception as error:
        return {"status": "invalid_explanation_output", "validation_error": str(error),
                "evidence_ids": [], "reason_unreviewed": None, "quote_locators": []}


def run(stage: str, model_path: Path, adapter: Path | None, weights_manifest: Path,
        gpu: str, operator: str, output: Path) -> int:
    if output.exists():
        raise RuntimeError("Output exists; preserve earlier run")
    prepared = [json.loads(line) for line in (HERE / "prepared_items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    plan = json.loads((HERE / "two_point_runtime_plan.json").read_text(encoding="utf-8"))
    if plan["status"] != "A100_REQUIRED_NOT_STARTED":
        raise RuntimeError("Unexpected or already consumed runtime plan")
    if plan["prepared_items_sha256"] != sha(HERE / "prepared_items.jsonl"):
        raise RuntimeError("Prepared item hash changed")
    if plan["settings"] != {"max_length": 5120, "max_new_tokens": 512,
                             "enable_thinking": False, "do_sample": False,
                             "retry_policy": "none; keep all first attempts"}:
        raise RuntimeError("Frozen settings changed")
    if stage == "classifier" and adapter is None:
        raise RuntimeError("Classifier requires Mbio adapter")
    if stage == "explainer" and adapter is not None:
        raise RuntimeError("Explainer must be independent base model")
    output.mkdir(parents=True)
    metadata = {"version": "supplement_two_point_runtime_20261029", "stage": stage,
                "started_at_utc": now(), "status": "running", "selected_case_ids": [x["case_id"] for x in prepared],
                "fixed_denominator": 20, "simulation": False, "source_validation": "frozen_prompt_and_PDF_locator_replay",
                "manifest_sha256": sha(HERE / "official_supplement_manifest.jsonl"), "runner_sha256": sha(Path(__file__))}
    write_json(output / "run_metadata.json", metadata)
    exit_code = 0
    try:
        with (output / "run.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            backend = HFBackend(stage, {"settings": {"max_length": 5120, "max_new_tokens": 512,
                "enable_thinking": False, "do_sample": False, "retry_policy": "none; keep all first attempts"}},
                model_path, adapter, weights_manifest, gpu, operator)
            metadata["actual_model"] = backend.identity
            write_json(output / "run_metadata.json", metadata)
            with (output / "responses.jsonl").open("w", encoding="utf-8") as stream:
                for item in prepared:
                    record = item[stage]
                    expected = contract.budget(backend.tokenizer, record)
                    response = {"case_id": item["case_id"], "input_sha256": record["input_sha256"], "attempted": True}
                    try:
                        raw, observed = backend.generate(record, expected)
                        response.update(raw_output=raw, observed_input=observed)
                        response["parsed"] = parse_classifier(raw) if stage == "classifier" else parse_explanation(raw, item["retrieval"]["candidates"])
                    except Exception as error:
                        exit_code = 1
                        response.update(error_type=type(error).__name__, error=str(error), raw_output=None,
                                        parsed={"status": "inference_failed", "label": None} if stage == "classifier"
                                        else {"status": "inference_failed", "evidence_ids": [], "reason_unreviewed": None, "quote_locators": []})
                        traceback.print_exc()
                    stream.write(json.dumps(response, ensure_ascii=False) + "\n")
                    stream.flush()
    except Exception as error:
        exit_code = 1
        metadata.update(error_type=type(error).__name__, error=str(error))
        traceback.print_exc()
    metadata.update(finished_at_utc=now(), status="finished" if exit_code == 0 else "failed", exit_code=exit_code)
    metadata["files_sha256"] = {p.name: sha(p) for p in output.iterdir() if p.is_file() and p.name != "run_metadata.json"}
    write_json(output / "run_metadata.json", metadata)
    (output / "exit_code.txt").write_text(str(exit_code) + "\n", encoding="utf-8")
    return exit_code


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("classifier", "explainer"))
    p.add_argument("--model-path", type=Path, required=True)
    p.add_argument("--weights-manifest", type=Path, required=True)
    p.add_argument("--adapter", type=Path)
    p.add_argument("--gpu", required=True)
    p.add_argument("--operator", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    return run(a.stage, a.model_path, a.adapter, a.weights_manifest, a.gpu, a.operator, a.output)


if __name__ == "__main__":
    raise SystemExit(main())
