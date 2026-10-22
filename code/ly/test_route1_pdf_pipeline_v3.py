"""CPU regressions with real PDF locators and explicitly simulated responses.

No model weights, GPU calls or human annotations. Fixture outputs are temporary
and never count as the 20 real runs or formal engineering/semantic acceptance.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import route1_pdf_pipeline_v3 as pipeline


class SimulatedGenerator:
    def __init__(self, stage, items, fail_after=None):
        self.stage, self.items, self.fail_after, self.calls = stage, items, fail_after, 0
        self.identity = {"simulation": True, "gpu_loaded": False, "weights_verified": False,
                         "role": "AUTOMATED_TEST_FIXTURE_NOT_A_MODEL"}

    def generate(self, record, expected):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("SIMULATED_INFERENCE_FAILURE_NO_GPU")
        if self.stage == "classifier":
            raw = '{"label":"ACCURATE"}'
        else:
            evidence = self.items[record["claim_id"]]["retrieval"]["candidates"][0]
            raw = json.dumps({"evidence_ids": [evidence["evidence_id"]],
                              "quotes": [{"evidence_id": evidence["evidence_id"], "quote": evidence["model_text"]}],
                              "reason": "AUTOMATED TEST FIXTURE: even a well-formatted reason is not human semantic acceptance."})
        return raw, {"input_tokens": expected["input_tokens"], "input_ids_sha256": expected["input_ids_sha256"], "simulation": True}


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = pipeline.source_gate.import_pdf(ARGS.pymupdf_dir)
        cls.items, cls.hashes = pipeline.load_prepared(ARGS.source_root, ARGS.prepared_dir, cls.pdf)
        cls.keyed = {i["case"]["case_id"]: i for i in cls.items}
        cls.plan = pipeline.read_json(ARGS.runtime_plan)
        # In-memory fixture only, keeps the real tokenizer measurements; no actual release is written.
        cls.plan["code_sha256"] = pipeline.code_hashes()
        cls.ids = [r["case_id"] for r in cls.plan["rows"] if not r["scope_hold"]][:3]
        cls.approvals = {"runtime_plan_sha256": pipeline.digest_file_plan(cls.plan), "rows": []}
        for row in cls.plan["rows"]:
            cls.approvals["rows"].append({"case_id": row["case_id"], "scope_sha256": row["scope_sha256"], "confirmed": True,
                                         "reviewer": "AUTOMATED_TEST_FIXTURE_NOT_A_HUMAN", "reviewed_at": "2000-01-01T00:00:00Z",
                                         "review_source": "SIMULATED_TEST_ONLY", "hold_resolution": "SIMULATED_SCOPE_RESOLUTION_NOT_REAL"})

    def release_file(self, root, selected=None):
        released = pipeline.release(self.plan, self.approvals, selected or self.ids)
        path = root / "SIMULATED_RELEASE_NOT_FOR_REAL_INFERENCE.json"
        pipeline.write_json(path, released)
        return path

    def test_fixed_20_pdf_points_and_no_torch_import(self):
        self.assertEqual(len(self.items), 20)
        self.assertEqual(len({r["case"]["pair_id"] for r in self.items}), 10)
        self.assertNotIn("torch", sys.modules)
        self.assertTrue(all(len(i["retrieval"]["candidates"]) == 10 for i in self.items))

    def test_pending_confirmations_and_drafts_never_load_backend(self):
        pending = copy.deepcopy(self.approvals)
        pending["rows"][0]["confirmed"] = False
        with self.assertRaisesRegex(ValueError, "Scope not confirmed"):
            pipeline.release(self.plan, pending)
        calls = []
        with tempfile.TemporaryDirectory(prefix="pdf_v3_SIMULATION_") as tmp:
            root = Path(tmp)
            draft = root / "draft.json"
            pipeline.write_json(draft, self.plan)
            with self.assertRaisesRegex(ValueError, "Draft input not released"):
                pipeline.run_stage("classifier", ARGS.source_root, ARGS.prepared_dir, draft, root / "not_created", self.pdf, lambda *a: calls.append(a))
            self.assertFalse((root / "not_created").exists())
        self.assertEqual(calls, [])

    def test_confirmation_is_bound_to_plan_and_scope(self):
        wrong = copy.deepcopy(self.approvals)
        wrong["runtime_plan_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different plan"):
            pipeline.release(self.plan, wrong)
        wrong = copy.deepcopy(self.approvals)
        wrong["rows"][1]["scope_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Scope not confirmed"):
            pipeline.release(self.plan, wrong, [wrong["rows"][1]["case_id"]])

    def test_unresolved_scope_hold_and_reduced_denominator_rejected(self):
        wrong = copy.deepcopy(self.approvals)
        wrong["rows"][0]["hold_resolution"] = None
        with self.assertRaisesRegex(ValueError, "hold not resolved"):
            pipeline.release(self.plan, wrong, [wrong["rows"][0]["case_id"]])
        smaller = copy.deepcopy(self.plan)
        smaller["rows"] = smaller["rows"][:3]
        with self.assertRaisesRegex(ValueError, "fixed 20-point"):
            pipeline.release(smaller, self.approvals)

    def test_unknown_or_duplicate_released_id_rejected(self):
        for selected in ([self.ids[0], self.ids[0]], ["foreign-case"]):
            with self.assertRaisesRegex(ValueError, "Unknown/duplicate"):
                pipeline.release(self.plan, self.approvals, selected)

    def test_classifier_failure_is_not_irrelevant_and_no_explanation_repair(self):
        self.assertEqual(pipeline.parse_classifier('{"failure_status":"insufficient_evidence"}'), {"status": "insufficient_evidence", "label": None})
        self.assertEqual(pipeline.parse_classifier('{"label":"ACCURATE","reason":"ignore this reason"}')["label"], "ACCURATE")
        for raw in ('{"label":"ACCURATE","label":"IRRELEVANT"}', '{"label":"NEI"}', '{"label":"ACCURATE","failure_status":"insufficient_evidence"}', 'prefix {"label":"ACCURATE"}'):
            self.assertEqual(pipeline.parse_classifier(raw)["status"], "invalid_classifier_output")

    def explanation(self, evidence, reason="TEST_FIXTURE: not an accepted semantic judgment"):
        return {"evidence_ids": [evidence["evidence_id"]], "quotes": [{"evidence_id": evidence["evidence_id"], "quote": evidence["model_text"]}], "reason": reason}

    def test_out_of_range_and_changed_quote_rejected(self):
        candidates = self.items[1]["retrieval"]["candidates"]
        obj = self.explanation(candidates[0])
        obj["evidence_ids"] = ["D01:S99"]
        self.assertEqual(pipeline.parse_explanation(json.dumps(obj), candidates)["status"], "invalid_explanation_output")
        obj = self.explanation(candidates[0])
        obj["quotes"][0]["quote"] += " NOT_IN_ORIGINAL_SOURCE"
        self.assertEqual(pipeline.parse_explanation(json.dumps(obj), candidates)["status"], "invalid_explanation_output")

    def test_prime_glyph_quote_maps_to_unchanged_pdf_text(self):
        item = self.items[2]
        evidence, = [c for c in item["retrieval"]["candidates"] if c["correction_patch_ids"]]
        result = pipeline.parse_explanation(json.dumps(self.explanation(evidence)), item["retrieval"]["candidates"])
        quote, = result["quote_locators"]
        self.assertIn("5′ end", quote["model_quote"])
        self.assertIn("50 end", quote["raw_quote"])
        self.assertEqual(quote["char_start"], evidence["pdf_fragments"][0]["char_start"])
        self.assertEqual(result["semantic_status"], "pending_human_review")

    def test_fluent_reason_with_valid_quote_stays_pending(self):
        candidates = self.items[1]["retrieval"]["candidates"]
        result = pipeline.parse_explanation(json.dumps(self.explanation(candidates[0], "UNSUPPORTED TEST ASSERTION: this proves every possible claim.")), candidates)
        self.assertEqual(result["status"], "structure_and_quotes_valid_pending_human_semantics")
        self.assertEqual(result["semantic_status"], "pending_human_review")
        self.assertNotIn("semantic_passed", result)

    def simulated_run(self, root, stage, released, fail_after=None):
        out = root / stage
        meta = pipeline.run_stage(stage, ARGS.source_root, ARGS.prepared_dir, released, out, self.pdf,
                                  lambda s, p: SimulatedGenerator(s, self.keyed, fail_after))
        return out, meta

    def test_simulated_success_has_fixed_denominator_but_no_real_acceptance(self):
        with tempfile.TemporaryDirectory(prefix="pdf_v3_SIMULATION_") as tmp:
            root = Path(tmp)
            released = self.release_file(root)
            c, cm = self.simulated_run(root, "classifier", released)
            e, em = self.simulated_run(root, "explainer", released)
            self.assertEqual(cm["exit_code"], 0)
            self.assertEqual(em["exit_code"], 0)
            summary = pipeline.assemble(ARGS.source_root, ARGS.prepared_dir, released, c, e, root / "assembled", self.pdf)
            self.assertEqual(summary["fixed_denominator"], 20)
            self.assertEqual(summary["attempted_classifier"], 3)
            self.assertEqual(summary["engineering_success"], 0)
            self.assertIsNone(summary["formal_location_rate"])
            records = pipeline.read_jsonl(root / "assembled/records.jsonl")
            self.assertEqual(len(records), 20)
            self.assertTrue(all(r["reason_for_display"] is None and r["confidence"] is None and r["classification_correct"] is None for r in records))

    def test_caught_runtime_failure_keeps_partial_and_unattempted_records(self):
        with tempfile.TemporaryDirectory(prefix="pdf_v3_SIMULATION_") as tmp:
            root = Path(tmp)
            released = self.release_file(root)
            run, meta = self.simulated_run(root, "classifier", released, fail_after=1)
            rows = pipeline.read_jsonl(run / "responses.jsonl")
            self.assertEqual(meta["exit_code"], 1)
            self.assertEqual([r["parsed"]["status"] for r in rows], ["valid_label", "inference_failed", "not_attempted_after_run_failure"])
            self.assertIsNotNone(rows[0]["raw_output"])
            self.assertEqual(len(rows), 3)
            self.assertEqual((run / "exit_code.txt").read_text().strip(), "1")

    def test_missing_explanation_does_not_erase_classifier(self):
        with tempfile.TemporaryDirectory(prefix="pdf_v3_SIMULATION_") as tmp:
            root = Path(tmp)
            released = self.release_file(root, [self.ids[0]])
            c, _ = self.simulated_run(root, "classifier", released)
            summary = pipeline.assemble(ARGS.source_root, ARGS.prepared_dir, released, c, None, root / "output", self.pdf)
            rows = pipeline.read_jsonl(root / "output/records.jsonl")
            item, = [r for r in rows if r["case_id"] == self.ids[0]]
            self.assertEqual(item["label"], "ACCURATE")
            self.assertIn("not_run", item["failure_status"])
            self.assertEqual(summary["engineering_success"], 0)

    def test_raw_response_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="pdf_v3_SIMULATION_") as tmp:
            root = Path(tmp)
            released = self.release_file(root)
            run, _ = self.simulated_run(root, "classifier", released)
            with (run / "responses.jsonl").open("a", encoding="utf-8") as stream:
                stream.write('{"case_id":"foreign-case"}\n')
            with self.assertRaisesRegex(ValueError, "Run artifact changed"):
                pipeline.read_stage(run, "classifier", pipeline.sha(released))

    def test_output_overwrite_and_foreign_actual_adapter_rejected(self):
        with tempfile.TemporaryDirectory(prefix="pdf_v3_SIMULATION_") as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "already exists"):
                pipeline.new_directory(root, ARGS.source_root, ARGS.prepared_dir)
            released = self.release_file(root)
            run, meta = self.simulated_run(root, "classifier", released)
            meta.update(simulation=False, actual_model={"role": "classifier", "base": "Qwen/Qwen3.8-27B", "revision": pipeline.preparation.BASE_REVISION,
                                                       "gpu_loaded": True, "weights_verified": True, "adapter_loaded": True, "adapter_sha256": "0" * 64})
            pipeline.write_json(run / "run_metadata.json", meta)
            with self.assertRaisesRegex(ValueError, "Actual adapter identity differs"):
                pipeline.read_stage(run, "classifier", pipeline.sha(released))

    def test_two_pdf_pair_mapping_and_reversed_direction(self):
        pair = self.items[1]["pair"]
        citing = ARGS.source_root / pair["citing"]["relative_path"]
        cited = ARGS.source_root / pair["cited"]["relative_path"]
        matched = pipeline.inspect_pair(ARGS.source_root, ARGS.prepared_dir, citing, cited, self.pdf)
        self.assertIn(self.items[1]["case"]["case_id"], matched["case_ids"])
        self.assertFalse(matched["model_run"])
        reversed_pair = pipeline.inspect_pair(ARGS.source_root, ARGS.prepared_dir, cited, citing, self.pdf)
        self.assertEqual(reversed_pair["status"], "pair_not_in_registered_scope")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("source-root", "prepared-dir", "runtime-plan", "pymupdf-dir"):
        p.add_argument("--" + name, type=Path, required=True)
    ARGS = p.parse_args()
    unittest.main(argv=[__file__], verbosity=2)
