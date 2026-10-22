"""Contract regression tests using real source PDFs and temporary test records.

Test retrieval fixtures are NOT semantic annotations or completed experiments.
Run with --source-root and optional --pymupdf-dir; no model or GPU is loaded.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import tempfile
import unittest

import run_route1_pdf_v3 as gate


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = gate.load_jsonl(ARGS.source_root / "case_manifest.jsonl")[0]
        cls.pair = gate.keyed(gate.load_jsonl(ARGS.source_root / "pair_manifest.jsonl"), "pair_id")[cls.case["pair_id"]]
        cls.replay = gate.PdfReplay(PDF)
        cls.citing = cls.replay.open(ARGS.source_root, cls.pair["citing"])
        cls.cited = cls.replay.open(ARGS.source_root, cls.pair["cited"])
        # Copy a real block as a mechanical fixture only. It is never asserted
        # relevant to the claim and is never written to delivery results.
        page = cls.cited[0]
        raw_page = page.get_text("text", sort=False)
        number, block = next((n, b) for n, b in enumerate(page.get_text("blocks", sort=False), 1)
                             if b[6] == 0 and str(b[4]).strip())
        raw = str(block[4])
        start = raw_page.find(raw)
        fragment = {"pdf_page": 1, "printed_page": None, "char_start": start,
                    "char_end_exclusive": start + len(raw), "raw_text": raw,
                    "raw_text_sha256": gate.text_sha(raw), "offset_basis": gate.OFFSET_BASIS,
                    "bbox_scope": gate.BBOX_SCOPE,
                    "source_blocks": [{"block_number": number, "bbox": [round(float(x), 3) for x in block[:4]]}]}
        cls.response = {
            "schema_version": gate.RETURN_SCHEMA, "case_id": cls.case["case_id"], "pair_id": cls.case["pair_id"],
            "cited_pdf_sha256": cls.pair["cited"]["sha256"], "retrieval_status": "ok",
            "parser": {"name": "PyMuPDF", "version": gate.PDF_VERSION},
            "retrieval_config": {"method": "TEST_FIXTURE_NOT_REAL_RETRIEVAL", "version": "test",
                                 "query": "mechanical fixture; not a semantic judgment", "top_k": 10,
                                 "corpus_pdf_sha256": cls.pair["cited"]["sha256"]},
            "retrieval_completed_at": "TEST_FIXTURE", "producer": "automated_test_only",
            "candidates": [{"evidence_id": "test:block1", "source_pdf_sha256": cls.pair["cited"]["sha256"],
                            "text": raw, "pdf_fragments": [fragment]}],
        }

    @classmethod
    def tearDownClass(cls):
        cls.replay.close()

    def validate(self, response):
        return gate.validate_retrieval(self.case, self.pair, response, self.replay, self.cited)

    def test_all_20_and_missing_states_remain_unknown(self):
        before = gate.sha(ARGS.source_root / "case_manifest.jsonl")
        with tempfile.TemporaryDirectory(prefix="pdf_gate_test_") as tmp:
            output = Path(tmp) / "result"
            receipt = gate.prepare(ARGS.source_root, output, PDF)
            self.assertEqual(receipt["physical_citation_points"], 20)
            self.assertEqual(receipt["pdf_pairs"], 10)
            self.assertEqual(receipt["unique_actual_pdfs_replayed"], 16)
            self.assertEqual(receipt["retrieval_status_counts"], {"awaiting_cited_retrieval": 20})
            self.assertIsNone(receipt["location_validity_rate"])
            self.assertIsNone(receipt["classification_accuracy"])
            self.assertFalse(receipt["gpu_used"])
            self.assertEqual((output / "classification.provisional.inputs.jsonl").read_text(), "")
            for row in gate.load_jsonl(output / "point_status.jsonl"):
                for field in ("model_prediction", "reason", "confidence", "score_support", "score_distort", "score_unrelated"):
                    self.assertIsNone(row[field])
                self.assertFalse(row["end_to_end_accepted"])
            with self.assertRaisesRegex(ValueError, "Output already exists"):
                gate.prepare(ARGS.source_root, output, PDF)
            self.assertEqual(receipt["generated_files_sha256"]["point_status.jsonl"], gate.sha(output / "point_status.jsonl"))
        self.assertEqual(before, gate.sha(ARGS.source_root / "case_manifest.jsonl"))

    def test_positive_locator_is_technical_only(self):
        status, evidence, _ = self.validate(self.response)
        self.assertEqual(status, "cited_locations_machine_replayed_pending_human_review")
        self.assertEqual(evidence[0]["evidence_id"], "D01:S01")
        self.assertEqual(evidence[0]["source_evidence_id"], "test:block1")
        self.assertNotIn("label", evidence[0])

    def test_missing_and_unavailable_do_not_become_irrelevant(self):
        self.assertEqual(self.validate(None)[0], "awaiting_cited_retrieval")
        row = copy.deepcopy(self.response)
        row.update(retrieval_status="no_reliable_evidence", candidates=[], note="original unavailable")
        self.assertEqual(self.validate(row)[0], "no_reliable_evidence")
        self.assertNotIn("IRRELEVANT", str(self.validate(row)))

    def test_cross_document_or_wrong_pair_rejected(self):
        for key in ("cited_pdf_sha256", "pair_id"):
            with self.subTest(field=key):
                row = copy.deepcopy(self.response)
                row[key] = "0" * 64
                with self.assertRaises(ValueError):
                    self.validate(row)
        row = copy.deepcopy(self.response)
        row["candidates"][0]["source_pdf_sha256"] = self.pair["citing"]["sha256"]
        with self.assertRaisesRegex(ValueError, "another PDF"):
            self.validate(row)

    def test_offsets_quote_page_hash_and_bounding_box_rejected(self):
        changes = {"pdf_page": 0, "char_start": -1, "char_end_exclusive": 10**9,
                   "raw_text": "changed quote", "raw_text_sha256": "0" * 64,
                   "offset_basis": "XML character offsets", "bbox_scope": "exact sentence"}
        for field, value in changes.items():
            with self.subTest(field=field):
                row = copy.deepcopy(self.response)
                row["candidates"][0]["pdf_fragments"][0][field] = value
                with self.assertRaises(ValueError):
                    self.validate(row)
        row = copy.deepcopy(self.response)
        row["candidates"][0]["pdf_fragments"][0]["source_blocks"][0]["bbox"][0] += 1
        with self.assertRaisesRegex(ValueError, "Bounding box"):
            self.validate(row)

    def test_duplicate_candidate_or_duplicate_span_rejected(self):
        row = copy.deepcopy(self.response)
        row["candidates"].append(copy.deepcopy(row["candidates"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate evidence_id"):
            self.validate(row)
        row["candidates"][1]["evidence_id"] = "another_ID_same_span"
        with self.assertRaisesRegex(ValueError, "Duplicate evidence span"):
            self.validate(row)

    def test_no_xml_only_evidence_and_no_text_rewrite(self):
        for field, value in (("pdf_fragments", []), ("text", "a rewritten paraphrase")):
            row = copy.deepcopy(self.response)
            row["candidates"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(row)

    def test_unknown_or_duplicate_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown case_id"):
            gate.keyed([{"case_id": "unlisted"}], "case_id", {self.case["case_id"]})
        with self.assertRaisesRegex(ValueError, "Duplicate case_id"):
            gate.keyed([self.case, self.case], "case_id")

    def test_marker_is_inside_its_context_and_target(self):
        marker = self.case["citation_marker_locator"][0]
        self.assertTrue(gate.marker_inside(marker, self.case["citing_context_raw_fragments"]))
        self.assertTrue(gate.marker_inside(marker, self.case["target_claim_scope_pdf_fragments"]))
        moved = copy.deepcopy(marker)
        moved["pdf_page"] += 1000
        self.assertFalse(gate.marker_inside(moved, self.case["citing_context_raw_fragments"]))

    def test_source_hash_and_path_escape_rejected(self):
        record = copy.deepcopy(self.pair["cited"])
        record["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "PDF hash mismatch"):
            self.replay.open(ARGS.source_root, record)
        with self.assertRaisesRegex(ValueError, "outside source package"):
            gate.relative_file(ARGS.source_root, "../README.txt")

    def test_unfixed_retrieval_config_rejected(self):
        for field, value in (("top_k", 0), ("query", None), ("version", None), ("corpus_pdf_sha256", "0" * 64)):
            row = copy.deepcopy(self.response)
            row["retrieval_config"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(row)

    def test_partial_return_retains_full_denominator_and_draft_only(self):
        with tempfile.TemporaryDirectory(prefix="pdf_gate_fixture_") as tmp:
            root = Path(tmp)
            fixture = root / "TEST_FIXTURE_NOT_A_REAL_RETRIEVAL.jsonl"
            value = copy.deepcopy(self.response)
            value["gold_label"] = "THIS_MUST_NOT_ENTER_MODEL_PROMPTS"
            gate.write_jsonl(fixture, [value])
            receipt = gate.prepare(ARGS.source_root, root / "output", PDF, fixture)
            self.assertEqual(receipt["physical_citation_points"], 20)
            self.assertEqual(receipt["retrieval_status_counts"]["awaiting_cited_retrieval"], 19)
            self.assertEqual(receipt["provisional_input_records"], 1)
            self.assertEqual(receipt["inference_ready_records"], 0)
            row, = gate.load_jsonl(root / "output" / "classification.provisional.inputs.jsonl")
            self.assertEqual(row["input_sha256"], gate.model_input_sha256(row["system_prompt"], row["user_prompt"]))
            self.assertNotIn("THIS_MUST_NOT_ENTER_MODEL_PROMPTS", row["system_prompt"] + row["user_prompt"])
            self.assertEqual(row["stage"], "provisional_input_not_approved_for_model_execution")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pymupdf-dir", type=Path)
    ARGS = parser.parse_args()
    PDF = gate.import_pdf(ARGS.pymupdf_dir)
    unittest.main(argv=[__file__], verbosity=2)
