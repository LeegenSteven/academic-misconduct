"""Import declared human reviews of fixed PDF20 outputs; never run a model.

Templates are unsigned. Agreement needs two separately submitted named opinions.
Disagreements need a resolution acknowledged by both people. This validates
recorded provenance, not a cryptographic proof of who operated the computer.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path

import route1_pdf_pipeline_v3 as pipeline

VERSION = 'route1_pdf_review_v3_20261021'
REVIEWERS = ('李云', '陈明进')
FIELDS = ('document_identity_valid', 'citation_scope_valid', 'location_valid',
          'explanation_semantic_valid', 'judged_label')
require = pipeline.require
digest = pipeline.digest


def text(value):
    return isinstance(value, str) and bool(value.strip())


def timestamp(value):
    require(text(value), 'Timezone-aware review time required')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('Invalid review time') from error
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'Timezone-aware review time required')


def valid_value(field, value):
    return value is None or (value in pipeline.LABELS if field == 'judged_label'
                             else type(value) is bool)


def actual_identity(identity, stage):
    if not isinstance(identity, dict):
        return False
    return (identity.get('simulation') is False and identity.get('gpu_loaded') is True
            and identity.get('weights_verified') is True and identity.get('role') == stage
            and identity.get('base') == 'Qwen/Qwen3.8-27B'
            and identity.get('revision') == pipeline.preparation.BASE_REVISION
            and identity.get('adapter_loaded') is (stage == 'classifier')
            and identity.get('adapter_sha256') == (pipeline.ADAPTER_SHA if stage == 'classifier' else None)
            and identity.get('enable_thinking') is False and identity.get('do_sample') is False)


def validate_records(plan, records):
    require(plan.get('version') == pipeline.VERSION and plan.get('fixed_denominator') == 20,
            'Fixed PDF20 runtime plan required')
    require(len(plan['rows']) == len(records) == 20, 'Keep all fixed 20 records')
    require(len({r['case_id'] for r in records}) == 20, 'Duplicate case ID')
    require([r['case_id'] for r in records] == [r['case_id'] for r in plan['rows']], 'Point set/order differs')
    require(len({digest(r['dedup_key']) for r in records}) == 20, 'Duplicate physical citation point')
    facts = {}
    for row, spec in zip(records, plan['rows']):
        cid = row['case_id']
        require(row['pair_id'] == spec['pair_id'], 'Pair identity differs')
        require(row.get('reason_for_display') is None and row.get('formal_end_to_end_accepted') is False,
                'Input must be original unreviewed assembled records')
        require(row.get('human_review') == {'李云': None, '陈明进': None, 'adjudication': None},
                'Do not replace previous human reviews; use original records and preserve review inputs')
        parsed_by_stage = {}
        actual = {}
        for stage, response_name, identity_name in (
                ('classifier', 'classifier_response', 'classifier_model'),
                ('explainer', 'explanation_response', 'explanation_model')):
            response = row.get(response_name)
            raw = response.get('raw_output') if response else None
            valid_status = 'valid_label' if stage == 'classifier' else 'structure_and_quotes_valid_pending_human_semantics'
            if response:
                require(response['case_id'] == cid and response['input_sha256'] == spec['stages'][stage]['input_sha256'],
                        'Stage response bound to wrong input')
                if raw is not None:
                    parsed = (pipeline.parse_classifier(raw) if stage == 'classifier'
                              else pipeline.parse_explanation(raw, row['retrieval']['candidates']))
                    require(parsed == response['parsed'], 'Parsed response differs from raw output')
                else:
                    parsed = response['parsed']
                    require(parsed.get('status') != valid_status, 'Missing raw output cannot be valid')
                observed = response.get('observed_input', {})
            else:
                parsed, observed = {}, {}
            parsed_by_stage[stage] = parsed
            actual[stage] = (bool(response and response.get('attempted'))
                             and actual_identity(row.get(identity_name), stage)
                             and observed.get('input_ids_sha256') == spec['stages'][stage]['input_ids_sha256']
                             and observed.get('input_tokens') == spec['stages'][stage]['input_tokens']
                             and bool(observed.get('generated_token_ids'))
                             and parsed.get('status') == valid_status)
        classifier, explanation = parsed_by_stage['classifier'], parsed_by_stage['explainer']
        require(row.get('label') == classifier.get('label'), 'Label differs from classifier')
        require(row.get('reason_unreviewed') == explanation.get('reason_unreviewed'), 'Reason differs from original explanation')
        require(row.get('evidence_ids', []) == explanation.get('evidence_ids', []), 'Selected evidence changed')
        require(row.get('quote_locators', []) == explanation.get('quote_locators', []), 'Quote locators changed')
        require(not row.get('engineering_success') or all(actual.values()), 'Claimed engineering success lacks actual stage proof')
        facts[cid] = {'classifier_valid': bool(actual['classifier']), 'explanation_valid': bool(actual['explainer']),
                      'technical_success': bool(row.get('engineering_success') and all(actual.values()))}
    return facts


def templates(records, records_sha, reviewer):
    require(reviewer in REVIEWERS, 'Unknown reviewer')
    return [{'version': VERSION, 'case_id': r['case_id'], 'records_file_sha256': records_sha,
             'case_record_sha256': digest(r), 'reviewer': reviewer, 'status': 'draft',
             'reviewed_at': None, 'review_source': None, 'prediction_seen': None,
             'assessments': {f: None for f in FIELDS}, 'basis': {f: None for f in FIELDS},
             'note': 'Unsigned template. Reviewer name is an assignment, not a signature.'} for r in records]


def validate_reviews(rows, reviewer, records, records_sha, facts):
    require(len(rows) == 20 and len({r['case_id'] for r in rows}) == 20, 'Keep all 20 review rows; duplicates rejected')
    require([r['case_id'] for r in rows] == [r['case_id'] for r in records], 'Review set/order differs')
    result = {}
    for opinion, record in zip(rows, records):
        require(opinion.get('version') == VERSION and opinion.get('reviewer') == reviewer, 'Wrong review version/person')
        require(opinion.get('records_file_sha256') == records_sha and opinion.get('case_record_sha256') == digest(record),
                'Stale review or changed record')
        values, basis = opinion['assessments'], opinion['basis']
        require(set(values) == set(basis) == set(FIELDS), 'Review fields missing/unknown')
        require(all(valid_value(f, values[f]) for f in FIELDS), 'Invalid assessment type/value')
        require(opinion['status'] in ('draft', 'submitted'), 'Unknown review status')
        if opinion['status'] == 'draft':
            require(all(v is None for v in values.values()) and all(v is None for v in basis.values())
                    and all(opinion[k] is None for k in ('reviewed_at', 'review_source', 'prediction_seen')),
                    'Unsigned draft must remain blank; explicitly submit actual opinions')
        else:
            timestamp(opinion['reviewed_at'])
            require(text(opinion['review_source']) and type(opinion['prediction_seen']) is bool,
                    'Actual review source and prediction exposure required')
            require(any(v is not None for v in values.values()), 'Submitted review is empty')
            for f in FIELDS:
                require(values[f] is None or text(basis[f]), 'Every judgment needs its own basis')
            if values['location_valid'] is True or values['explanation_semantic_valid'] is True:
                require(facts[record['case_id']]['explanation_valid'], 'Cannot accept absent/invalid/simulated model explanation')
        result[opinion['case_id']] = opinion
    return result


def resolve(field, left, right, adjudication):
    lv = left['assessments'][field] if left['status'] == 'submitted' else None
    rv = right['assessments'][field] if right['status'] == 'submitted' else None
    if lv is None or rv is None:
        return None, 'pending_two_reviews'
    if lv == rv:
        return lv, 'two_reviewers_agree'
    if adjudication and field in adjudication['decisions']:
        return adjudication['decisions'][field], 'joint_adjudication'
    return None, 'disagreement'


def validate_adjudication(row, record, records_sha, left, right, facts):
    require(row.get('version') == VERSION and row.get('records_file_sha256') == records_sha
            and row.get('case_record_sha256') == digest(record), 'Adjudication bound to wrong record')
    require(row.get('review_row_sha256') == {REVIEWERS[0]: digest(left), REVIEWERS[1]: digest(right)},
            'Adjudication does not bind both current original opinions')
    require(row.get('status') == 'jointly_confirmed', 'Draft adjudication cannot resolve a disagreement')
    timestamp(row['resolved_at'])
    require(set(row['confirmations']) == set(REVIEWERS), 'Both people must confirm adjudication')
    for reviewer in REVIEWERS:
        confirmation = row['confirmations'][reviewer]
        timestamp(confirmation['confirmed_at'])
        require(text(confirmation['review_source']), 'Adjudication confirmation source required')
    require(bool(row['decisions']) and set(row['decisions']) <= set(FIELDS), 'Empty/unknown adjudication decision')
    for f, value in row['decisions'].items():
        require(value is not None and valid_value(f, value) and text(row['basis'].get(f)), 'Adjudication needs decision and basis')
        require(resolve(f, left, right, None)[1] == 'disagreement', 'Only two submitted conflicting judgments can be adjudicated')
        if f in ('location_valid', 'explanation_semantic_valid') and value is True:
            require(facts[record['case_id']]['explanation_valid'], 'Invalid explanation cannot be adjudicated into a valid output')


def merge_reviews(plan, records, records_sha, left_rows, right_rows, adjudications=()):
    facts = validate_records(plan, records)
    left = validate_reviews(left_rows, REVIEWERS[0], records, records_sha, facts)
    right = validate_reviews(right_rows, REVIEWERS[1], records, records_sha, facts)
    require(len({a['case_id'] for a in adjudications}) == len(adjudications), 'Duplicate adjudication')
    by_id = {r['case_id']: r for r in records}
    adj = {a['case_id']: a for a in adjudications}
    require(set(adj) <= set(by_id), 'Unknown adjudication ID')
    for cid, row in adj.items():
        validate_adjudication(row, by_id[cid], records_sha, left[cid], right[cid], facts)
    output, disagreements = [], []
    for record in records:
        cid = record['case_id']
        row = copy.deepcopy(record)
        resolved = {f: resolve(f, left[cid], right[cid], adj.get(cid)) for f in FIELDS}
        values = {f: v[0] for f, v in resolved.items()}
        statuses = {f: v[1] for f, v in resolved.items()}
        conflicts = [f for f, s in statuses.items() if s == 'disagreement']
        if conflicts:
            disagreements.append({'version': VERSION, 'case_id': cid, 'records_file_sha256': records_sha,
                'case_record_sha256': digest(record), 'review_row_sha256': {REVIEWERS[0]: digest(left[cid]), REVIEWERS[1]: digest(right[cid])},
                'status': 'draft', 'conflicting_fields': conflicts, 'decisions': {}, 'basis': {},
                'resolved_at': None, 'confirmations': {name: {'confirmed_at': None, 'review_source': None} for name in REVIEWERS}})
        engineering = (facts[cid]['technical_success'] and values['document_identity_valid'] is True
                       and values['citation_scope_valid'] is True)
        identity_scope_ok = values['document_identity_valid'] is True and values['citation_scope_valid'] is True
        # Preserve independent opinions: a location failure is not an automatic
        # semantic failure, and an unresolved scope is not a new human judgment.
        location = values['location_valid']
        semantic = values['explanation_semantic_valid']
        correct = (record['label'] == values['judged_label']
                   if facts[cid]['classifier_valid'] and values['judged_label'] is not None and identity_scope_ok else None)
        show = engineering and location is True and semantic is True
        row.update(human_review={REVIEWERS[0]: left[cid], REVIEWERS[1]: right[cid], 'adjudication': adj.get(cid)},
                   review_resolution={'values': values, 'statuses': statuses}, engineering_human_accepted=bool(engineering),
                   locator_human_check=location, classification_correct=correct,
                   explanation_semantic_status='passed_human_review' if semantic is True else
                       'failed_human_review' if semantic is False else 'pending_human_review',
                   reason_for_display=record['reason_unreviewed'] if show else None,
                   formal_end_to_end_accepted=bool(show and correct is not None), independent_blind_claimed=False)
        output.append(row)
    reviewed_location = sum(r['locator_human_check'] is not None for r in output)
    valid_location = sum(r['locator_human_check'] is True for r in output)
    semantic_reviewed = sum(r['explanation_semantic_status'] != 'pending_human_review' for r in output)
    semantic_passed = sum(r['explanation_semantic_status'] == 'passed_human_review' for r in output)
    evaluated = sum(r['classification_correct'] is not None for r in output)
    correct = sum(r['classification_correct'] is True for r in output)
    summary = {'version': VERSION, 'fixed_denominator': 20,
        'attempted_classifier': sum(bool(r.get('classifier_response') and r['classifier_response'].get('attempted')) for r in records),
        'attempted_explainer': sum(bool(r.get('explanation_response') and r['explanation_response'].get('attempted')) for r in records),
        'engineering_technical_success': sum(f['technical_success'] for f in facts.values()),
        'engineering_human_accepted': sum(r['engineering_human_accepted'] for r in output),
        'location_reviewed': reviewed_location, 'location_pending': 20-reviewed_location,
        'location_valid': valid_location if reviewed_location else None,
        'location_confirmed_valid_fraction_fixed20': valid_location/20 if reviewed_location else None,
        'formal_location_rate': valid_location/20 if reviewed_location == 20 else None,
        'location_80pct_target_met': valid_location >= 16 if reviewed_location == 20 else None,
        'explanation_semantic_reviewed': semantic_reviewed, 'explanation_semantic_passed': semantic_passed if semantic_reviewed else None,
        'explanation_semantic_rate_reviewed': semantic_passed/semantic_reviewed if semantic_reviewed else None,
        'classification_correct': correct if evaluated else None, 'classification_evaluated_denominator': evaluated,
        'classification_pending_or_no_valid_prediction': 20-evaluated, 'classification_accuracy': correct/evaluated if evaluated else None,
        'unresolved_disagreement_points': len(disagreements),
        'formal_end_to_end_accepted': sum(r['formal_end_to_end_accepted'] for r in output),
        'declared_review_provenance_only': True, 'model_run_performed_by_review_tool': False,
        'note': 'Fixed 20 remain visible. Counts, location, explanation semantics and classification are separate; partial rates are labeled. Actual human identity is not cryptographically attested.'}
    return output, summary, disagreements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('init', 'merge'))
    for name in ('runtime-plan', 'records', 'review-liyun', 'review-chenmingjin', 'adjudications', 'output-dir'):
        parser.add_argument('--'+name, type=Path, required=name in ('runtime-plan', 'records', 'output-dir'))
    args = parser.parse_args()
    plan, records = pipeline.read_json(args.runtime_plan), pipeline.read_jsonl(args.records)
    records_sha = pipeline.sha(args.records)
    validate_records(plan, records)
    if args.stage == 'merge':
        require(args.review_liyun and args.review_chenmingjin, 'Both review files required; blanks stay pending')
        rows, summary, disagreements = merge_reviews(plan, records, records_sha,
            pipeline.read_jsonl(args.review_liyun), pipeline.read_jsonl(args.review_chenmingjin),
            pipeline.read_jsonl(args.adjudications) if args.adjudications else [])
    require(not args.output_dir.exists(), 'Output exists; preserve original reviews')
    protected = [p.resolve().parent for p in (args.runtime_plan, args.records, args.review_liyun,
                 args.review_chenmingjin, args.adjudications) if p]
    require(not any(args.output_dir.resolve().is_relative_to(p) for p in protected), 'Output must be outside source receipt/review directories')
    args.output_dir.mkdir(parents=True)
    if args.stage == 'init':
        for reviewer, name in zip(REVIEWERS, ('review_liyun.jsonl', 'review_chenmingjin.jsonl')):
            pipeline.write_jsonl(args.output_dir/name, templates(records, records_sha, reviewer))
        print('UNSIGNED_REVIEW_TEMPLATES_CREATED rows_per_reviewer=20 submitted=0 no_model_run=true')
    else:
        pipeline.write_jsonl(args.output_dir/'records.reviewed.jsonl', rows)
        pipeline.write_json(args.output_dir/'summary.json', summary)
        pipeline.write_jsonl(args.output_dir/'adjudication_needed.unsigned.jsonl', disagreements)
        print(json.dumps(summary, ensure_ascii=False))
    inputs = {name: {'path': str(p.resolve()), 'sha256': pipeline.sha(p)} for name, p in vars(args).items()
              if isinstance(p, Path) and name != 'output_dir'}
    pipeline.write_json(args.output_dir/'provenance.json', {'version': VERSION, 'inputs': inputs,
        'code_sha256': pipeline.sha(__file__), 'runtime_plan_sha256': pipeline.sha(args.runtime_plan),
        'outputs_sha256': {p.name: pipeline.sha(p) for p in args.output_dir.iterdir() if p.is_file()}})


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit(f'REVIEW_IMPORT_REJECTED {type(error).__name__}: {error}')
