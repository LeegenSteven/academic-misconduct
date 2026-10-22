"""Synthetic in-memory review fixtures only; no human opinions or model runs.

All files created by CLI tests live in auto-cleaned temporary directories.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import route1_pdf_review_v3 as review


def fixture():
    plan = {'version': review.pipeline.VERSION, 'fixed_denominator': 20, 'rows': []}
    rows = []
    for n in range(20):
        cid = f'SIMULATED_NOT_A_REAL_POINT_{n:02d}'
        stages = {s: {'input_sha256': review.digest([n, s]), 'input_ids_sha256': review.digest([n, s, 'tokens']),
                      'input_tokens': n+100} for s in ('classifier', 'explainer')}
        plan['rows'].append({'case_id': cid, 'pair_id': f'SIMULATED_PAIR_{n//2}', 'stages': stages})
        evidence = {'evidence_id': 'D01:S01', 'model_text': 'Synthetic unit-test evidence.',
            'raw_text': 'Synthetic unit-test evidence.', 'source_pdf_sha256': 'a'*64, 'correction_patch_ids': [],
            'pdf_fragments': [{'pdf_page': 1, 'printed_page': None, 'char_start': 10, 'source_blocks': []}]}
        raw_e = json.dumps({'evidence_ids': ['D01:S01'], 'quotes': [{'evidence_id': 'D01:S01',
                           'quote': evidence['model_text']}], 'reason': 'TEST FIXTURE, NOT A REAL EXPLANATION.'})
        parsed_e = review.pipeline.parse_explanation(raw_e, [evidence])
        row = {'case_id': cid, 'pair_id': f'SIMULATED_PAIR_{n//2}', 'dedup_key': f'SIMULATED_KEY_{n}',
               'retrieval': {'candidates': [evidence]}, 'reason_for_display': None, 'formal_end_to_end_accepted': False,
               'human_review': {'李云': None, '陈明进': None, 'adjudication': None}, 'label': 'ACCURATE',
               'reason_unreviewed': parsed_e['reason_unreviewed'], 'evidence_ids': parsed_e['evidence_ids'],
               'quote_locators': parsed_e['quote_locators'], 'engineering_success': True}
        for stage, raw in (('classifier', '{"label":"ACCURATE"}'), ('explainer', raw_e)):
            identity = {'simulation': False, 'gpu_loaded': True, 'weights_verified': True, 'role': stage,
                        'base': 'Qwen/Qwen3.8-27B', 'revision': review.pipeline.preparation.BASE_REVISION,
                        'adapter_loaded': stage == 'classifier',
                        'adapter_sha256': review.pipeline.ADAPTER_SHA if stage == 'classifier' else None,
                        'enable_thinking': False, 'do_sample': False,
                        'operator': 'SYNTHETIC UNIT TEST ONLY; NO ACTUAL GPU OR PERSON'}
            row[stage+'_model' if stage == 'classifier' else 'explanation_model'] = identity
            row[stage+'_response' if stage == 'classifier' else 'explanation_response'] = {
                'case_id': cid, 'input_sha256': stages[stage]['input_sha256'], 'raw_output': raw, 'attempted': True,
                'observed_input': {'input_ids_sha256': stages[stage]['input_ids_sha256'], 'input_tokens': n+100,
                                   'generated_token_ids': [1, 2, 3]},
                'parsed': review.pipeline.parse_classifier(raw) if stage == 'classifier' else parsed_e}
        rows.append(row)
    sha = review.digest(rows)
    left = review.templates(rows, sha, '李云')
    right = review.templates(rows, sha, '陈明进')
    return plan, rows, sha, left, right


def submit(row, label='ACCURATE', **changes):
    row.update(status='submitted', reviewed_at='2000-01-01T00:00:00Z',
               review_source='AUTOMATED_TEST_FIXTURE_NOT_A_PERSON', prediction_seen=True)
    row['assessments'] = {f: label if f == 'judged_label' else True for f in review.FIELDS}
    row['assessments'].update(changes)
    row['basis'] = {f: 'SYNTHETIC TEST BASIS' if row['assessments'][f] is not None else None for f in review.FIELDS}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.rows, self.sha, self.left, self.right = fixture()

    def merge(self, adj=()):
        return review.merge_reviews(self.plan, self.rows, self.sha, self.left, self.right, adj)

    def rebind(self):
        self.sha = review.digest(self.rows)
        self.left = review.templates(self.rows, self.sha, '李云')
        self.right = review.templates(self.rows, self.sha, '陈明进')

    def test_unsigned_templates_do_not_accept_or_display(self):
        rows, summary, adj = self.merge()
        self.assertEqual(summary['fixed_denominator'], 20)
        self.assertEqual(summary['engineering_human_accepted'], 0)
        self.assertIsNone(summary['classification_accuracy'])
        self.assertIsNone(summary['formal_location_rate'])
        self.assertEqual(summary['location_pending'], 20)
        self.assertTrue(all(r['reason_for_display'] is None for r in rows))
        self.assertFalse(adj)
        self.assertNotIn('torch', sys.modules)

    def test_one_person_never_counts_as_two(self):
        submit(self.left[0])
        rows, summary, _ = self.merge()
        self.assertIsNone(rows[0]['classification_correct'])
        self.assertEqual(summary['classification_evaluated_denominator'], 0)
        self.assertIsNone(rows[0]['reason_for_display'])

    def test_classification_error_can_have_engineering_and_semantic_success(self):
        submit(self.left[0], label='NOT_ACCURATE')
        submit(self.right[0], label='NOT_ACCURATE')
        rows, summary, _ = self.merge()
        self.assertFalse(rows[0]['classification_correct'])
        self.assertEqual(summary['engineering_human_accepted'], 1)
        self.assertIsNotNone(rows[0]['reason_for_display'])
        self.assertTrue(rows[0]['formal_end_to_end_accepted'])
        self.assertEqual(summary['classification_accuracy'], 0.0)
        self.assertIsNone(summary['formal_location_rate'])
        self.assertEqual(summary['location_confirmed_valid_fraction_fixed20'], 1/20)

    def test_semantic_disagreement_blocks_explanation_but_keeps_classification(self):
        submit(self.left[0])
        submit(self.right[0], explanation_semantic_valid=False)
        rows, summary, adj = self.merge()
        self.assertTrue(rows[0]['classification_correct'])
        self.assertIsNone(rows[0]['reason_for_display'])
        self.assertEqual(summary['unresolved_disagreement_points'], 1)
        self.assertEqual(adj[0]['status'], 'draft')
        self.assertIsNone(adj[0]['confirmations']['陈明进']['confirmed_at'])

    def test_joint_adjudication_requires_both_acknowledgements(self):
        submit(self.left[0])
        submit(self.right[0], explanation_semantic_valid=False)
        _, _, drafts = self.merge()
        adj = drafts[0]
        adj.update(status='jointly_confirmed', resolved_at='2000-01-02T00:00:00Z',
                   decisions={'explanation_semantic_valid': False}, basis={'explanation_semantic_valid': 'SYNTHETIC RESOLUTION'})
        adj['confirmations']['李云'] = {'confirmed_at': '2000-01-02T00:00:00Z', 'review_source': 'TEST ONLY'}
        with self.assertRaisesRegex(ValueError, 'review time'):
            self.merge([adj])
        adj['confirmations']['陈明进'] = {'confirmed_at': '2000-01-02T00:00:00Z', 'review_source': 'TEST ONLY'}
        rows, summary, remaining = self.merge([adj])
        self.assertEqual(rows[0]['explanation_semantic_status'], 'failed_human_review')
        self.assertIsNone(rows[0]['reason_for_display'])
        self.assertEqual(summary['unresolved_disagreement_points'], 0)
        self.assertEqual(remaining, [])
        self.right[0]['basis']['explanation_semantic_valid'] = 'CHANGED OPINION'
        with self.assertRaisesRegex(ValueError, 'current original opinions'):
            self.merge([adj])

    def test_unknown_duplicate_wrong_person_and_stale_reviews_rejected(self):
        for mutation, message in (
            (lambda: self.left[0].update(case_id='FOREIGN'), 'set/order'),
            (lambda: self.left[0].update(case_id=self.left[1]['case_id']), 'duplicates'),
            (lambda: self.right[0].update(reviewer='李云'), 'person'),
            (lambda: self.left[0].update(case_record_sha256='0'*64), 'Stale'),
            (lambda: self.left[0].update(records_file_sha256='0'*64), 'Stale')):
            with self.subTest(message=message):
                self.setUp()
                mutation()
                with self.assertRaisesRegex(ValueError, message):
                    self.merge()

    def test_missing_basis_naive_time_exposure_and_draft_filled_rejected(self):
        for mutation, message in (
            (lambda r: r['basis'].update(location_valid=None), 'basis'),
            (lambda r: r.update(reviewed_at='2000-01-01T00:00:00'), 'Timezone'),
            (lambda r: r.update(prediction_seen=None), 'exposure'),
            (lambda r: r.update(status='draft'), 'draft')):
            with self.subTest(message=message):
                self.setUp()
                submit(self.left[0])
                mutation(self.left[0])
                with self.assertRaisesRegex(ValueError, message):
                    self.merge()

    def test_partial_16_reviews_cannot_shrink_formal_denominator(self):
        for n in range(16):
            submit(self.left[n]); submit(self.right[n])
        _, summary, _ = self.merge()
        self.assertEqual(summary['location_valid'], 16)
        self.assertEqual(summary['location_pending'], 4)
        self.assertEqual(summary['location_confirmed_valid_fraction_fixed20'], 0.8)
        self.assertIsNone(summary['formal_location_rate'])
        self.assertIsNone(summary['location_80pct_target_met'])

    def test_16_of_20_uses_fixed_denominator_not_only_valid_points(self):
        for n in range(20):
            submit(self.left[n], location_valid=n < 16)
            submit(self.right[n], location_valid=n < 16)
        rows, summary, _ = self.merge()
        self.assertEqual(summary['formal_location_rate'], 0.8)
        self.assertTrue(summary['location_80pct_target_met'])
        self.assertEqual(summary['formal_end_to_end_accepted'], 16)
        self.assertIsNone(rows[-1]['reason_for_display'])

    def test_invalid_explanation_cannot_be_human_overridden(self):
        self.rows[0].update(explanation_response=None, explanation_model=None, reason_unreviewed=None,
                            evidence_ids=[], quote_locators=[], engineering_success=False)
        self.rebind()
        submit(self.left[0]); submit(self.right[0])
        with self.assertRaisesRegex(ValueError, 'absent/invalid/simulated'):
            self.merge()
        for opinion in (self.left[0], self.right[0]):
            opinion['assessments'].update(location_valid=None, explanation_semantic_valid=None)
        rows, summary, _ = self.merge()
        self.assertTrue(rows[0]['classification_correct'])
        self.assertIsNone(rows[0]['reason_for_display'])
        self.assertEqual(summary['engineering_human_accepted'], 0)

    def test_four_outcomes_do_not_infer_one_review_from_another(self):
        submit(self.left[0], location_valid=False, explanation_semantic_valid=None)
        submit(self.right[0], location_valid=False, explanation_semantic_valid=None)
        rows, summary, _ = self.merge()
        self.assertFalse(rows[0]['locator_human_check'])
        self.assertEqual(rows[0]['explanation_semantic_status'], 'pending_human_review')
        self.assertIsNone(summary['explanation_semantic_passed'])
        self.assertTrue(rows[0]['classification_correct'])
        self.assertIsNone(rows[0]['reason_for_display'])

    def test_simulated_stage_cannot_be_counted_as_real_engineering(self):
        self.rows[0]['classifier_model']['simulation'] = True
        with self.assertRaisesRegex(ValueError, 'actual stage proof'):
            self.merge()
        self.rows[0]['engineering_success'] = False
        self.rebind()
        submit(self.left[0]); submit(self.right[0])
        rows, summary, _ = self.merge()
        self.assertIsNone(rows[0]['classification_correct'])
        self.assertIsNone(rows[0]['reason_for_display'])
        self.assertEqual(summary['engineering_technical_success'], 19)

    def test_raw_tampering_token_drift_pair_and_duplicate_points_rejected(self):
        for mutation, message in (
            (lambda: self.rows[0]['classifier_response'].update(raw_output='{"label":"IRRELEVANT"}'), 'raw output'),
            (lambda: self.rows[0]['classifier_response']['observed_input'].update(input_ids_sha256='bad'), 'stage proof'),
            (lambda: self.rows[0].update(pair_id='other'), 'Pair'),
            (lambda: self.rows[0].update(dedup_key=self.rows[1]['dedup_key']), 'physical')):
            with self.subTest(message=message):
                self.setUp(); mutation()
                with self.assertRaisesRegex(ValueError, message):
                    self.merge()

    def test_cli_templates_and_merge_do_not_touch_originals(self):
        with tempfile.TemporaryDirectory(prefix='SIMULATED_REVIEW_NOT_REAL_') as td:
            root = Path(td)
            source = root/'source'; source.mkdir()
            review.pipeline.write_json(source/'plan.json', self.plan)
            review.pipeline.write_jsonl(source/'records.jsonl', self.rows)
            before = {p.name: p.read_bytes() for p in source.iterdir()}
            command = [sys.executable, str(Path(review.__file__)), 'init', '--runtime-plan', str(source/'plan.json'),
                       '--records', str(source/'records.jsonl'), '--output-dir', str(root/'templates')]
            initialized = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertIn('submitted=0', initialized.stdout)
            merged = subprocess.run(command[:2]+['merge']+command[3:-2]+[
                '--review-liyun', str(root/'templates/review_liyun.jsonl'), '--review-chenmingjin',
                str(root/'templates/review_chenmingjin.jsonl'), '--output-dir', str(root/'merged')],
                capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(merged.returncode, 0, merged.stderr)
            summary = json.loads((root/'merged/summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['formal_end_to_end_accepted'], 0)
            repeated = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})


if __name__ == '__main__':
    unittest.main(verbosity=2)
