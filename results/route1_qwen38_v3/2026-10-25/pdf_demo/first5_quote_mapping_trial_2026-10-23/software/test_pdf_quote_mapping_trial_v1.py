"""Boundary and counterexample tests for layout-only quote mapping."""
import unittest
from pdf_quote_mapping_trial_v1 import match_quote, unwrap_outer_json_fence


class QuoteMappingTests(unittest.TestCase):
    def test_exact_interval(self):
        r = match_quote("before sample after", "sample")
        self.assertEqual(r["status"], "exact_unique")
        self.assertEqual((r["matches"][0]["source_start"], r["matches"][0]["source_end"]), (7, 13))

    def test_overlapping_repeats_are_ambiguous(self):
        self.assertEqual(match_quote("aaa", "aa")["match_count"], 2)

    def test_whitespace_maps_back(self):
        r = match_quote("A\n  report", "A report")
        self.assertTrue(r["unique_mapping"])
        self.assertEqual(r["matches"][0]["character_map"][1]["source_end"], 4)

    def test_word_boundaries_are_preserved(self):
        self.assertFalse(match_quote("a part", "apart")["unique_mapping"])

    def test_real_hyphen_is_retained(self):
        r = match_quote("single-\nstrand", "single-strand")
        self.assertTrue(r["unique_mapping"])
        self.assertFalse(r["line_join_review_required"])
        self.assertIn("line_break_after_retained_hyphen", [c["kind"] for c in r["matches"][0]["transformations"]])

    def test_removed_line_hyphen_needs_review(self):
        r = match_quote("struc-\ntural", "structural")
        self.assertTrue(r["unique_mapping"])
        self.assertTrue(r["line_join_review_required"])

    def test_lexical_line_join_is_never_automatic(self):
        r = match_quote("re-\ncreation", "recreation")
        self.assertTrue(r["line_join_review_required"])

    def test_soft_hyphen(self):
        r = match_quote("beta\u00adcoronavirus", "betacoronavirus")
        self.assertTrue(r["unique_mapping"])
        self.assertEqual(r["matches"][0]["transformations"][0]["kind"], "soft_hyphen_removed")

    def test_inline_hyphen_cannot_disappear(self):
        self.assertFalse(match_quote("re-creation", "recreation")["unique_mapping"])

    def test_changed_number_rejected(self):
        self.assertEqual(match_quote("144 000 structures", "100 000 structures")["status"], "not_matched")

    def test_negation_inside_sentence_not_deleted(self):
        self.assertEqual(match_quote("A is not effective", "A is effective")["status"], "not_matched")

    def test_changed_word_rejected(self):
        self.assertEqual(match_quote("RNA genome", "DNA genome")["status"], "not_matched")

    def test_minus_sign_cannot_disappear(self):
        self.assertFalse(match_quote("value -5", "value 5")["unique_mapping"])

    def test_numeric_line_hyphen_not_joined(self):
        self.assertFalse(match_quote("1-\n2", "12")["unique_mapping"])

    def test_citation_numbers_inside_quote_not_erased(self):
        self.assertFalse(match_quote("identified.10,11 More", "identified. More")["unique_mapping"])

    def test_quote_may_end_before_citation_numbers(self):
        self.assertTrue(match_quote("identified.10,11 More", "identified")["unique_mapping"])

    def test_normalized_repeats_are_ambiguous(self):
        r = match_quote("A\nB; A\tB", "A B")
        self.assertEqual(r["status"], "ambiguous")
        self.assertEqual(r["match_count"], 2)

    def test_case_not_folded(self):
        self.assertFalse(match_quote("RNA", "rna")["unique_mapping"])

    def test_regex_punctuation_is_literal(self):
        self.assertEqual(match_quote("x [a+b]", "[a+b]")["status"], "exact_unique")

    def test_empty_quote_rejected(self):
        with self.assertRaises(ValueError):
            match_quote("text", " ")

    def test_only_complete_json_fence_unwrapped(self):
        f = chr(96) * 3
        raw = f + 'json\n{"x":1}\n' + f
        self.assertEqual(unwrap_outer_json_fence(raw), ('{"x":1}', True))
        for invalid in ("prefix\n" + raw, raw + "\nsuffix", f + "python\n{}\n" + f, f + "json\n{}"):
            self.assertEqual(unwrap_outer_json_fence(invalid), (invalid, False))


if __name__ == "__main__":
    unittest.main()

