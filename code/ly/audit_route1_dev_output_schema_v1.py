"""Audit response JSON without changing the frozen Route 1 label metrics.

Checks all four currently available M0/Mscv Dev output files against the
frozen input-side evidence IDs. Mbio can be added after its outputs exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LABELS = {"ACCURATE", "NOT_ACCURATE", "IRRELEVANT"}
REQUIRED = {"label", "evidence_ids", "reason", "confidence"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_by_id(path: Path) -> dict[str, dict]:
    rows = {}
    with path.open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            claim_id = str(row["claim_id"])
            if claim_id in rows:
                raise ValueError(f"Duplicate claim_id {claim_id!r} in {path}:{number}")
            rows[claim_id] = row
    if not rows:
        raise ValueError(f"Empty JSONL: {path}")
    return rows


def response_errors(raw: object, allowed: set[str], predicted: object) -> tuple[dict, list[str]]:
    if not isinstance(raw, str):
        return {}, ["raw_output_not_string"]
    try:
        response = json.loads(raw)
    except (TypeError, ValueError):
        return {}, ["not_json_object"]
    if not isinstance(response, dict):
        return {}, ["not_json_object"]

    errors = []
    label = response.get("label")
    if not isinstance(label, str) or label not in LABELS:
        errors.append("invalid_label")
    elif label != predicted:
        errors.append("label_differs_from_scored_prediction")

    evidence_ids = response.get("evidence_ids")
    if not isinstance(evidence_ids, list) or any(not isinstance(value, str) for value in evidence_ids):
        errors.append("invalid_evidence_ids_type")
    else:
        if len(evidence_ids) > 5:
            errors.append("too_many_evidence_ids")
        if len(set(evidence_ids)) != len(evidence_ids):
            errors.append("duplicate_evidence_ids")
        if not set(evidence_ids) <= allowed:
            errors.append("evidence_id_outside_candidates")

    reason = response.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 120:
        errors.append("invalid_reason")

    confidence = response.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append("invalid_confidence")
    return response, errors


def audit_pair(input_path: Path, prediction_path: Path) -> dict:
    inputs = jsonl_by_id(input_path)
    predictions = jsonl_by_id(prediction_path)
    if set(inputs) != set(predictions):
        raise ValueError(
            f"Input/prediction IDs differ for {prediction_path}: "
            f"missing={sorted(set(inputs) - set(predictions))[:5]}, "
            f"extra={sorted(set(predictions) - set(inputs))[:5]}"
        )

    issue_counts: Counter[str] = Counter()
    issue_examples: dict[str, list[str]] = {}
    full_field_count = label_only_count = valid_count = 0
    for claim_id, prediction in predictions.items():
        allowed_ids = inputs[claim_id].get("allowed_evidence_ids")
        if not isinstance(allowed_ids, list) or any(not isinstance(value, str) for value in allowed_ids):
            raise ValueError(f"Invalid allowed_evidence_ids for {claim_id} in {input_path}")
        response, errors = response_errors(prediction.get("raw_output"), set(allowed_ids), prediction.get("pred"))
        full_field_count += REQUIRED <= set(response)
        label_only_count += set(response) == {"label"}
        valid_count += not errors
        for issue in errors:
            issue_counts[issue] += 1
            examples = issue_examples.setdefault(issue, [])
            if len(examples) < 5:
                examples.append(claim_id)

    return {
        "total": len(predictions),
        "fields_present": full_field_count,
        "label_only": label_only_count,
        "full_schema_valid": valid_count,
        "issues": dict(sorted(issue_counts.items())),
        "issue_example_claim_ids": issue_examples,
        "inputs_sha256": sha256_file(input_path),
        "predictions_sha256": sha256_file(prediction_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True, help="Directory containing dev/{dataset}/{model}/ outputs")
    parser.add_argument(
        "--data-root", type=Path,
        default=REPO_ROOT / "results/route1_qwen38_v2/2026-10-15",
        help="Frozen v2 dataset directory",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON audit report; refuses to overwrite")
    args = parser.parse_args()

    report = {"scope": "supplemental Dev response schema audit; label metrics unchanged", "units": {}}
    for domain in ("sciciteval", "sarol"):
        report["units"][domain] = {}
        for model in ("M0", "Mscv"):
            input_path = args.data_root / domain / "dev.inputs.jsonl"
            prediction_path = args.run_root / "dev" / domain / model / f"{model}_dev_predictions.jsonl"
            report["units"][domain][model] = audit_pair(input_path, prediction_path)

    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    print(content, end="")


if __name__ == "__main__":
    main()
