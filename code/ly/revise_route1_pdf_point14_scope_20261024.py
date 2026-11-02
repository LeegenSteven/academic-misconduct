"""Keep point 14's quantities, endpoint and reference group in primary scope.

Create a new unreleased draft. Preserve the previous CPU-verified draft and all
original PDF/input/model records. No new human label or GPU execution.
"""
from collections import Counter
import copy
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import sys

import run_route1_pdf_v3 as gate
import prepare_pdf20_scope_inputs_20261020 as prep
import route1_pdf_pipeline_v3 as runtime
from replay_cmj_pdf20_retrieval_20261020 import original_functions


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.workspace.resolve(), args.output_dir.resolve()
    repo = Path(__file__).resolve().parents[2]
    demo = repo / "results/route1_qwen38_v3/2026-10-25/pdf_demo"
    previous = demo / "remaining13_preparation_2026-10-24"
    source = root / "10.19-11.2/路线一PDF独立清单_20261020"
    gate.require(not output.exists(), "New r2 output directory required")
    os.environ.update(USE_TORCH="0", USE_TF="0", HF_HUB_OFFLINE="1", CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false")
    sys.path.insert(0, str(root / "tmp/pdf20_tokenizer_deps_20261020"))
    sys.path.insert(0, str(root / "tmp/pdf20_bm25_replay_deps_20261020"))
    import rank_bm25
    gate.require(importlib.metadata.version("rank-bm25") == "0.2.2", "Wrong BM25 version")
    parent = gate.read_json(previous / "summary.json")
    protected = gate.read_json(previous / "protected_original_files_sha256.json")
    for name, expected in parent["generated_files_sha256"].items():
        gate.require(gate.sha(previous / name) == expected, "Previous draft changed")
        protected[str(previous / name)] = expected
    protected[str(previous / "summary.json")] = gate.sha(previous / "summary.json")
    for path, expected in protected.items():
        gate.require(gate.sha(path) == expected, "Protected original changed")
    scopes = gate.load_jsonl(previous / "scope_review.draft.jsonl")
    retrieval = gate.load_jsonl(previous / "retrieval.draft.jsonl")
    classification = gate.load_jsonl(previous / "classification.draft.inputs.jsonl")
    explanation = gate.load_jsonl(previous / "explanation.draft.inputs.jsonl")
    changes = gate.load_jsonl(previous / "remaining13_changes.jsonl")
    budgets = gate.read_json(previous / "two_stage_budget_report.json")
    before = copy.deepcopy(scopes[13])
    gate.require(len(before["primary_scope_pieces"]) == len(before["context_only_pieces"]) == 1, "Unexpected point14 source structure")
    numeric_piece = scopes[13]["context_only_pieces"].pop()
    gate.require(all(s in numeric_piece["text"] for s in ("1.5", "5.6", "39.9", "dementia", "reference group")), "Lost numerical or endpoint restriction")
    scopes[13]["primary_scope_pieces"].append(numeric_piece)
    scopes[13]["prepared_query"] = "\n".join(p["text"] for p in scopes[13]["primary_scope_pieces"])
    scopes[13]["boundary_reason"] = "将Specifically句的风险比、痴呆终点与参考组并入核查范围，避免仅作指代背景时被忽略；保留所有原数值。"
    policy = gate.read_json(previous / "policy_before_cpu_retrieval.json")
    policy.update(prepared_data_revision="r2_point14_quantities_in_primary_scope", parent_policy_sha256=gate.sha(previous / "policy_before_cpu_retrieval.json"),
                  created_before_cpu_retrieval_at_utc=datetime.now(timezone.utc).isoformat(),
                  revision_reason=scopes[13]["boundary_reason"])
    output.mkdir(parents=True)
    gate.write_json(output / "policy_before_cpu_retrieval.json", policy)
    functions = original_functions(source / "2026-10-20_PDF20点被引检索/route1_pdf20_cited_retrieval_v1.py", source)
    gate.require(Counter(functions["tokenize"](retrieval[13]["query"])) == Counter(functions["tokenize"](scopes[13]["prepared_query"])), "Query term multiset changed unexpectedly")
    cited_sha = retrieval[13]["candidates"][0]["source_pdf_sha256"]
    blocks, short, refs = functions["load_blocks"](cited_sha)
    index = rank_bm25.BM25Okapi([functions["tokenize"](b["raw_text"]) for b in blocks], k1=1.2, b=.75)
    scores = index.get_scores(functions["tokenize"](scopes[13]["prepared_query"]))
    picked = sorted(range(len(blocks)), key=lambda i: scores[i], reverse=True)[:10]
    for old, chosen in zip(retrieval[13]["candidates"], picked):
        block = blocks[chosen]
        gate.require(old["raw_text_sha256"] == block["raw_text_sha256"] and old["pdf_fragments"][0]["char_start"] == block["char_start"], "Unexpected candidate change")
        gate.require(old["retrieval_score"] == round(float(scores[chosen]), 6), "Unexpected rounded score change")
    retrieval[13]["query"] = scopes[13]["prepared_query"]
    tokenizer = runtime.tokenizer_for(root / "tmp/pdf20_official_tokenizer_snapshot_20261020", root / "tmp/pdf20_tokenizer_deps_20261020")
    changed_stage_fingerprints = 0
    for n, (scope, returned, classifier, explainer, budget) in enumerate(zip(scopes, retrieval, classification, explanation, budgets["rows"]), 1):
        user = prep.user_prompt(scope["primary_scope_pieces"], scope["context_only_pieces"], returned["candidates"])
        old_input = classifier["input_sha256"]
        classifier.update(user_prompt=user, input_sha256=gate.model_input_sha256(prep.SYSTEM_PROMPT, user))
        exp_user = user.rsplit("\n仅对目标引用范围返回 label JSON；不能可靠判定时返回规定的 failure_status。", 1)[0] + "\n仅返回规定的证据摘录和解释 JSON，不输出分类标签。"
        explainer.update(user_prompt=exp_user, input_sha256=gate.model_input_sha256(runtime.EXPLANATION_SYSTEM, exp_user))
        stages = {role: {"input_sha256": rec["input_sha256"], **runtime.budget(tokenizer, rec)} for role, rec in (("classifier", classifier), ("explainer", explainer))}
        for role in stages:
            changed_stage_fingerprints += stages[role]["input_ids_sha256"] != budget["stages"][role]["input_ids_sha256"]
        if n != 14:
            gate.require(old_input == classifier["input_sha256"] and stages == budget["stages"], "Other point payload changed")
        classifier["expected_input_ids_sha256"] = stages["classifier"]["input_ids_sha256"]
        classifier["within_budget"] = stages["classifier"]["within_budget"]
        budget.update(scope_sha256=runtime.digest({k: scope[k] for k in ("case_id", "pair_id", "dedup_key", "primary_scope_pieces", "context_only_pieces")}), stages=stages)
        gate.require(all(x["within_budget"] for x in stages.values()), "Budget overflow")
    gate.require(changed_stage_fingerprints == 2, "Exactly point14's two stages should change")
    row = next(x for x in changes if x["point_number"] == 14)
    row.update(proposal=scopes[13]["boundary_reason"], primary_after=[p["text"] for p in scopes[13]["primary_scope_pieces"]], context_after=[],
               classifier_input_sha256=classification[13]["input_sha256"],
               classifier_required_tokens=budgets["rows"][13]["stages"]["classifier"]["required_total"],
               explainer_required_tokens=budgets["rows"][13]["stages"]["explainer"]["required_total"])
    gate.write_jsonl(output / "scope_review.draft.jsonl", scopes)
    gate.write_jsonl(output / "retrieval.draft.jsonl", retrieval)
    gate.write_jsonl(output / "classification.draft.inputs.jsonl", classification)
    gate.write_jsonl(output / "explanation.draft.inputs.jsonl", explanation)
    gate.write_jsonl(output / "remaining13_changes.jsonl", changes)
    gate.write_json(output / "two_stage_budget_report.json", budgets)
    gate.write_json(output / "source_wrap_patches.draft.json", gate.read_json(previous / "source_wrap_patches.draft.json"))
    gate.write_json(output / "protected_original_files_sha256.json", protected)
    revision = {"version": "r2_point14_quantities_in_primary_scope", "case_id": scopes[13]["case_id"],
                "reason": scopes[13]["boundary_reason"], "before_primary": [p["text"] for p in before["primary_scope_pieces"]],
                "before_context": [p["text"] for p in before["context_only_pieces"]],
                "after_primary": [p["text"] for p in scopes[13]["primary_scope_pieces"]], "after_context": [],
                "same_source_fragments": True, "same_BM25_term_multiset_and_candidates_and_scores": True,
                "changed_stage_fingerprints": 2, "other_points_changed": 0, "human_label": None, "model_run": False,
                "parent_summary_sha256": gate.sha(previous / "summary.json")}
    gate.write_json(output / "point14_scope_role_revision.json", revision)
    current = copy.deepcopy(parent)
    current.update(prepared_data_revision=revision["version"], parent_preparation_summary_sha256=revision["parent_summary_sha256"],
                   recorded_at_utc=datetime.now(timezone.utc).isoformat(), source_script_sha256=gate.sha(__file__),
                   maximum_required_tokens_remaining13=max(max(x["classifier_required_tokens"], x["explainer_required_tokens"]) for x in changes),
                   generated_files_sha256={p.name: gate.sha(p) for p in output.iterdir() if p.is_file()})
    gate.write_json(output / "summary.json", current)
    (output / "runtime_adapter").mkdir()
    (output / "runtime_adapter/text_layer_corrections.json").write_bytes((previous / "runtime_adapter/text_layer_corrections.json").read_bytes())
    for path, expected in protected.items():
        gate.require(gate.sha(path) == expected, "Original modified during r2 preparation")
    print("POINT14_SCOPE_R2_PREPARED two_fingerprints_changed=2 other_points_changed=0 candidates_unchanged=true model_runs=0")


if __name__ == "__main__":
    main()
