"""Boundary tests for the new source-mapping parser, using synthetic text."""
import json
import unittest

import route1_pdf_explanation_parser_v4_20261024 as parser


def candidate(text):
    digest = parser.text_sha(text)
    return {"evidence_id": "D01:S01", "source_pdf_sha256": "0" * 64,
            "raw_text": text, "model_text": text,
            "raw_text_sha256": digest, "model_text_sha256": digest,
            "pdf_fragments": [{"raw_text": text, "raw_text_sha256": digest,
                               "pdf_page": 1, "char_start": 100, "char_end_exclusive": 100 + len(text),
                               "source_blocks": [{"block_number": 1, "bbox": [0, 0, 10, 10]}],
                               "bbox_scope": "whole block", "offset_basis": "Unicode codepoints, half-open"}]}


def response(quote):
    return json.dumps({"evidence_ids": ["D01:S01"], "quotes": [{"evidence_id": "D01:S01", "quote": quote}], "reason": "test evidence"})


class ParserBoundaries(unittest.TestCase):
    def parsed(self, source, quote):
        return parser.parse_explanation(response(quote), [candidate(source)])

    def test_exact_quote_returns_source_and_pending_semantics(self):
        result = self.parsed("Alpha beta", "Alpha beta")
        self.assertEqual(result["status"], "structure_and_source_mapping_valid_pending_human_semantics")
        self.assertEqual((result["quote_locators"][0]["char_start"], result["quote_locators"][0]["char_end_exclusive"]), (100, 110))
        self.assertFalse(result["semantic_verified"])
        self.assertIsNone(result["quote_locators"][0]["human_mapping_confirmed"])

    def test_only_complete_outer_fence_is_accepted(self):
        text = "```json\n" + response("Alpha") + "\n```"
        self.assertTrue(parser.parse_explanation(text, [candidate("Alpha")])["status"].startswith("structure_"))
        for bad in (text[:-3], "preface\n" + text, text + "\nafterword", "```python\n" + response("Alpha") + "\n```"):
            with self.subTest(bad=bad[:20]):
                self.assertEqual(parser.parse_explanation(bad, [candidate("Alpha")])["status"], "invalid_explanation_output")

    def test_whitespace_maps_without_erasing_word_boundary(self):
        self.assertTrue(self.parsed("Alpha \n beta", "Alpha beta")["status"].startswith("structure_"))
        self.assertEqual(self.parsed("Alpha beta", "Alphabeta")["status"], "invalid_explanation_output")

    def test_retained_lexical_hyphen_is_preserved(self):
        self.assertTrue(self.parsed("alpha-\nbeta", "alpha-beta")["status"].startswith("structure_"))
        self.assertEqual(self.parsed("alpha-beta", "alphabeta")["status"], "invalid_explanation_output")

    def test_unreviewed_line_join_is_rejected(self):
        result = self.parsed("exper-\nimental", "experimental")
        self.assertEqual(result["validation_error"], "line_end_join_not_whitelisted")

    def test_case_number_punctuation_or_negation_rewrite_is_rejected(self):
        for source, quote in (("Alpha", "alpha"), ("12.5", "12.6"), ("a-b", "a−b"), ("not supported", "now supported")):
            with self.subTest(source=source, quote=quote):
                self.assertEqual(self.parsed(source, quote)["status"], "invalid_explanation_output")

    def test_short_quote_cannot_infer_semantic_acceptance(self):
        # A literal substring can omit important surrounding context. That is a
        # semantic review problem, never an automatic label or acceptance.
        result = self.parsed("not supported", "supported")
        self.assertTrue(result["status"].startswith("structure_"))
        self.assertFalse(result["semantic_verified"])

    def test_overlapping_repeated_source_is_ambiguous(self):
        self.assertEqual(self.parsed("aaaa", "aaa")["status"], "invalid_explanation_output")

    def test_json_duplicates_nonfinite_and_incomplete_are_rejected(self):
        texts = [response("Alpha")[:-1], '{"failure_status":"insufficient_evidence","failure_status":"insufficient_evidence"}',
                 '{"evidence_ids":[],"quotes":[],"reason":NaN}']
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(parser.parse_explanation(text, [candidate("Alpha")])["status"], "invalid_explanation_output")

    def test_unknown_or_duplicate_ids_are_rejected(self):
        obj = json.loads(response("Alpha"))
        for ids in (["D01:S99"], ["D01:S01", "D01:S01"], [1]):
            obj["evidence_ids"] = ids
            self.assertEqual(parser.parse_explanation(json.dumps(obj), [candidate("Alpha")])["status"], "invalid_explanation_output")

    def test_candidate_hash_tampering_is_rejected(self):
        item = candidate("Alpha")
        item["raw_text_sha256"] = "0" * 64
        self.assertEqual(parser.parse_explanation(response("Alpha"), [item])["validation_error"], "candidate_text_hash_mismatch")

    def test_insufficient_evidence_is_not_promoted(self):
        result = parser.parse_explanation('{"failure_status":"insufficient_evidence"}', [candidate("Alpha")])
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertFalse(result["semantic_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
