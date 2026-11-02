"""Freeze actual PDF citation locations before new inference; never read labels."""
from __future__ import annotations

import bisect
import collections
import difflib
import hashlib
import json
import re
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pdf_locator_deps'))
import pymupdf as fitz


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_text(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def rows(path, values):
    Path(path).write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in values), encoding='utf-8')


def copy_unchanged(source, destination):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        assert sha(destination) == sha(source), ('Refuse source overwrite', destination)
    else:
        shutil.copyfile(source, destination)
    return str(destination)


def canonical(text):
    out, offsets = [], []
    for index, char in enumerate(text):
        for expanded in unicodedata.normalize('NFKC', char).casefold():
            if expanded.isalnum():
                out.append(expanded)
                offsets.append(index)
    return ''.join(out), offsets


def canon(text):
    return canonical(text)[0]


def normalized_pdf_text(text):
    value = unicodedata.normalize('NFKC', text).replace('\u00ad', '')
    value = re.sub(r'(?<=[A-Za-z])-\s+(?=[A-Za-z])', '', value)
    return re.sub(r'\s+', ' ', value).strip()


DOCUMENTS = {}


def load_pdf(record):
    path = Path(record['pdf_source']['path'])
    h = sha(path)
    assert h == record['pdf_source']['sha256']
    if h in DOCUMENTS:
        return DOCUMENTS[h]
    pages, starts, blocks, all_text = [], [], [], ''
    with fitz.open(path) as pdf:
        for page_no, page in enumerate(pdf, 1):
            text = page.get_text('text', sort=False)
            starts.append(len(all_text))
            pages.append(text)
            all_text += text + '\f'
            cursor = 0
            for n, b in enumerate(page.get_text('blocks', sort=False)):
                if len(b) > 6 and b[6] != 0:
                    continue
                raw = str(b[4])
                start = text.find(raw, cursor)
                if start < 0:
                    raise ValueError('Text/block extraction mismatch')
                cursor = start + len(raw)
                blocks.append({'pdf_page': page_no, 'block_number': n + 1,
                               'char_start': start, 'char_end_exclusive': cursor,
                               'bbox': [round(float(v), 3) for v in b[:4]],
                               'raw_text': raw, 'raw_text_sha256': digest_text(raw)})
    canonical_text, mapping = canonical(all_text)
    first_three = canon('\n'.join(pages[:3]))
    identity = {'title_found_in_first_three_pages': canon(record['title']) in first_three,
                'doi_found_in_first_three_pages': bool(record.get('doi')) and canon(record['doi']) in first_three}
    if not all(identity.values()):
        raise ValueError(('PDF identity check pending', record['pmcid'], identity))
    data = {'sha256': h, 'path': str(path), 'pages': pages, 'starts': starts,
            'raw': all_text, 'canonical': canonical_text, 'canonical_mapping': mapping,
            'blocks': blocks, 'identity_checks': identity}
    cache = BASE / 'pdf_text' / h
    cache.mkdir(parents=True, exist_ok=True)
    for n, text in enumerate(pages, 1):
        (cache / f'page_{n:03d}.txt').write_text(text, encoding='utf-8')
    rows(cache / 'blocks.jsonl', blocks)
    DOCUMENTS[h] = data
    return data


def raw_fragments(doc, intervals):
    merged = []
    for a, b in sorted(intervals):
        if merged and (a <= merged[-1][1] or not canon(doc['raw'][merged[-1][1]:a])):
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    result = []
    for start, end in merged:
        for index, page_start in enumerate(doc['starts']):
            text = doc['pages'][index]
            a, b = max(start, page_start), min(end, page_start + len(text))
            if a >= b:
                continue
            a, b = a - page_start, b - page_start
            matching_blocks = [x for x in doc['blocks'] if x['pdf_page'] == index + 1
                               and x['char_start'] < b and a < x['char_end_exclusive']]
            assert matching_blocks
            quote = text[a:b]
            result.append({'pdf_page': index + 1, 'printed_page': None,
                           'char_start': a, 'char_end_exclusive': b,
                           'raw_text': quote, 'raw_text_sha256': digest_text(quote),
                           'source_blocks': [{'block_number': x['block_number'], 'bbox': x['bbox']} for x in matching_blocks],
                           'bbox_scope': 'whole intersecting text blocks, not exact sentence boxes',
                           'offset_basis': 'PyMuPDF page.get_text(text, sort=False); Unicode code points; zero-based half-open'})
    return result


def serialize_paragraph(paragraph):
    pieces, length, spans = [], 0, {}
    def walk(node):
        nonlocal length
        start = length
        if node.text:
            pieces.append(node.text)
            length += len(node.text)
        for child in node:
            walk(child)
            if child.tail:
                pieces.append(child.tail)
                length += len(child.tail)
        if node.tag == 'xref':
            spans[id(node)] = (start, length, node.get('rid', ''), ''.join(node.itertext()))
    walk(paragraph)
    return ''.join(pieces), spans


def paragraph_location(doc, paragraph, target):
    xml_text, xrefs = serialize_paragraph(paragraph)
    c, cm = canonical(xml_text)
    a, b, _, marker_xml = xrefs[id(target)]
    ta, tb = bisect.bisect_left(cm, a), bisect.bisect_left(cm, b)
    if ta == tb:
        raise ValueError('Target citation has no printable marker characters')
    absolute = doc['canonical'].find(c)
    notes = []
    if absolute >= 0 and doc['canonical'].find(c, absolute + 1) < 0:
        alignment = {n: absolute + n for n in range(len(c))}
    else:
        # Use long, unique XML paragraph anchors only to find the PDF span.
        # Actual claim text below always comes from unchanged PDF fragments.
        head, tail = c[:60], c[-60:]
        start = doc['canonical'].find(head)
        end = doc['canonical'].find(tail)
        if (start < 0 or end < start or doc['canonical'].count(head) != 1
                or doc['canonical'].count(tail) != 1 or end - start > len(c) + 16000):
            raise ValueError('Unique full-paragraph PDF anchors not established')
        candidate = doc['canonical'][start:end + len(tail)]
        matcher = difflib.SequenceMatcher(None, c, candidate, autojunk=False)
        alignment = {}
        for op, i, j, k, l in matcher.get_opcodes():
            if op == 'equal':
                alignment.update({x: start + k + x - i for x in range(i, j)})
            elif op == 'insert':
                notes.append({'type': 'PDF_layout_material_between_paragraph_fragments',
                              'canonical_character_count': l - k})
            elif op == 'delete':
                # XML may expand a printed numeric reference range, e.g. 5-7.
                # Permit only *other* bibliography markers, never claim values.
                raw_a, raw_b = cm[i], cm[j - 1] + 1
                covering = [v for key, v in xrefs.items() if key != id(target)
                            and v[0] <= raw_a and raw_b <= v[1]]
                if not covering or not c[i:j].isdigit():
                    raise ValueError('Unresolved XML/PDF paragraph content difference')
                notes.append({'type': 'XML_other_reference_range_expansion',
                              'xml_reference_marker': covering[0][3], 'xml_rid': covering[0][2]})
            else:
                raise ValueError('Unresolved XML/PDF content replacement; no fuzzy acceptance')
    if any(n not in alignment for n in range(ta, tb)):
        raise ValueError('Target marker itself is not fully mapped to the PDF')
    values = sorted(set(alignment.values()))
    runs = []
    for value in values:
        if runs and value == runs[-1][1]:
            runs[-1][1] += 1
        else:
            runs.append([value, value + 1])
    raw_intervals = [(doc['canonical_mapping'][s], doc['canonical_mapping'][e - 1] + 1) for s, e in runs]
    context = raw_fragments(doc, raw_intervals)
    marker_indices = [alignment[n] for n in range(ta, tb)]
    marker = raw_fragments(doc, [(doc['canonical_mapping'][min(marker_indices)],
                                  doc['canonical_mapping'][max(marker_indices)] + 1)])
    # Suggest a sentence boundary without hiding the original paragraph.
    # Mask reference strings for segmentation so a post-period superscript stays
    # with the preceding claim. This is a review proposal, not human sign-off.
    masked = list(xml_text)
    for start, end, _, _ in xrefs.values():
        masked[start:end] = ' ' * (end - start)
    boundary_text = ''.join(masked)
    boundaries = [0] + [m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])', boundary_text)] + [len(xml_text)]
    interval = max(0, bisect.bisect_right(boundaries, a) - 1)
    sentence_start, sentence_end = boundaries[interval], boundaries[interval + 1]
    scoped = sorted({alignment[n] for n in alignment if sentence_start <= cm[n] < sentence_end})
    scoped_runs = []
    for value in scoped:
        if scoped_runs and value == scoped_runs[-1][1]:
            scoped_runs[-1][1] += 1
        else:
            scoped_runs.append([value, value + 1])
    scope = raw_fragments(doc, [(doc['canonical_mapping'][s], doc['canonical_mapping'][e - 1] + 1)
                                for s, e in scoped_runs])
    assert scope and any(m['pdf_page'] == f['pdf_page'] and f['char_start'] <= m['char_start']
                         and m['char_end_exclusive'] <= f['char_end_exclusive'] for m in marker for f in scope)
    return context, marker, notes, marker_xml, xml_text, scope


def mark_target(context, markers):
    result = []
    for fragment in context:
        value = fragment['raw_text']
        positions = [(m['char_start'] - fragment['char_start'], m['char_end_exclusive'] - fragment['char_start'])
                     for m in markers if m['pdf_page'] == fragment['pdf_page']
                     and fragment['char_start'] <= m['char_start']
                     and m['char_end_exclusive'] <= fragment['char_end_exclusive']]
        for a, b in sorted(positions, reverse=True):
            value = value[:a] + '[[TARGET_REFERENCE]]' + value[a:b] + '[[/TARGET_REFERENCE]]' + value[b:]
        result.append(value)
    value = normalized_pdf_text('\n'.join(result))
    assert value.count('[[TARGET_REFERENCE]]') == len(markers)
    return value


def full_numeric_citation_group(doc, markers):
    if len(markers) != 1 or not markers[0]['raw_text'].isdigit():
        return markers
    marker = markers[0]
    page = doc['pages'][marker['pdf_page'] - 1]
    for found in re.finditer(r'\d+(?:\s*[,\-\u2013\u2014]\s*\d+)*', page):
        if found.start() <= marker['char_start'] and marker['char_end_exclusive'] <= found.end():
            start = doc['starts'][marker['pdf_page'] - 1]
            return raw_fragments(doc, [(start + found.start(), start + found.end())])
    return markers


def main():
    acquisition = read(BASE / 'source_acquisition.json')
    articles = {r['pmcid']: r for r in acquisition['records']}
    policy = read(BASE / 'selection_policy_before_pdf_processing.json')
    pairs = list(policy['candidate_pairs'])
    added_pairs = []
    old_root = ROOT / '路线一PDF定位_20261018'
    citing_acq = read(old_root / 'edge0104/source_acquisition.json')['files'][0]
    for name, number, cited_id in [('newpair_001_R7_PMC5958625', 7, 'PMC5958625'),
                                    ('newpair_002_R40_PMC9671808', 40, 'PMC9671808')]:
        folder = old_root / name
        acq = read(folder / 'source_acquisition.json')
        identity = read(folder / 'source_identity_and_scope_check.json')
        for pmcid, old_record in [('PMC11350039', citing_acq), (cited_id, acq['cited'])]:
            if pmcid in articles:
                continue
            original = Path(old_record['path'])
            if not original.exists():
                original = folder / 'sources' / (pmcid + '.1.pdf')
            assert sha(original) == old_record['sha256']
            target_dir = BASE / 'sources' / (pmcid + '.1')
            copied_pdf = copy_unchanged(original, target_dir / original.name)
            meta_original = (old_root / 'edge0104/sources' if pmcid == 'PMC11350039' else folder / 'sources') / (pmcid + '.1.json')
            meta = read(meta_original)
            assert meta['pmcid'] == pmcid
            copy_unchanged(meta_original, target_dir / meta_original.name)
            assert hashlib.md5(Path(copied_pdf).read_bytes()).hexdigest() == old_record['public_metadata_md5']
            record = {'pmcid': pmcid, 'version': pmcid + '.1', 'status': 'existing_source_reused',
                      'title': old_record['title'], 'doi': old_record['doi'],
                      'license_code': old_record['license_code'], 'is_manuscript': meta.get('is_manuscript'),
                      'pdf_source': {'path': copied_pdf, 'sha256': sha(copied_pdf),
                                     'requested_url': old_record['pdf_url'], 'original_path': str(original),
                                     'official_md5_verified': True, 'official_md5': old_record['public_metadata_md5']}}
            if pmcid == 'PMC11350039':
                xml_original = folder / 'sources/PMC11350039_20261011_snapshot.xml'
                copied_xml = copy_unchanged(xml_original, target_dir / xml_original.name)
                assert sha(copied_xml) == identity['xml_sha256']
                record['xml_source'] = {'path': copied_xml, 'sha256': sha(copied_xml),
                                        'requested_url': 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11350039/fullTextXML',
                                        'note': 'Retained 2026-10-11 XML helper snapshot; all final locations verified on actual fixed PDF'}
            articles[pmcid] = record
        added_pairs.append({'candidate_id': name, 'citing_pmcid': 'PMC11350039',
                            'cited_pmcid': cited_id, 'citing_xml_locator': f'bibliography_xref=alz13859-bib-{number:04d}; paragraph containing xref',
                            'origin_identity_file': str(folder / 'source_identity_and_scope_check.json')})
    policy_v2 = {'date': '2026-10-20', 'supersedes': 'selection_policy_before_pdf_processing.json',
                 'change_reason': 'Original pool has at most 15 citation occurrences with both main PDFs, below target20; supplement two already-prepared different-reference pairs, without looking at labels or predictions.',
                 'added_pairs': added_pairs, 'selection': 'round robin in original candidate order plus added pair order; PDF marker location order within each pair',
                 'target': 20, 'reserve_and_failures': 'retain all; never replace after seeing classification results',
                 'domain_before_predictions': 'biomedical subject contexts, including structural bioinformatics; planned classifier Mbio checkpoint-100',
                 'label_or_prediction_used_for_selection': False}
    pp = BASE / 'selection_policy_v2_before_new_inference.json'
    if pp.exists():
        assert read(pp) == policy_v2, 'Do not silently change the policy'
    else:
        dump(pp, policy_v2)
    pairs += added_pairs
    for article in articles.values():
        for key in ('pdf_source', 'xml_source'):
            source = article.get(key)
            if source:
                source['relative_path'] = Path(source['path']).relative_to(BASE).as_posix()
                source['path_resolution'] = 'batch root / relative_path; absolute path retained as local acquisition history'
    dump(BASE / 'target_scope_proposal_policy_before_inference.json', {
        'date': '2026-10-20', 'selection_set_changed': False,
        'proposal_rule': 'Mask XML bibliography-marker strings, split at sentence punctuation before next capital; associate post-period marker with preceding sentence; map back to exact PDF fragments.',
        'full_original_paragraph_preserved': True,
        'specific_target_occurrence_marked': True,
        'human_scope_review_required': True,
        'model_predictions_used': False})
    legacy = old_root / '原五对10点_被引检索交接_20261019/施引检索任务_10点.jsonl'
    old_points = [json.loads(x) for x in legacy.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    legacy_pairs = {(r['source_pdfs']['citing']['sha256'], r['source_pdfs']['cited']['sha256']) for r in old_points}
    legacy_pmcpairs = {('PMC9825514', 'PMC9825450'), ('PMC9252913', 'PMC9214472'),
                       ('PMC10653297', 'PMC10735173'), ('PMC10158837', 'PMC9825424'),
                       ('PMC11350039', 'PMC10352931')}
    prepared, failures, pair_rows, all_points = collections.OrderedDict(), [], [], []
    for pair in pairs:
        cid, did = pair['citing_pmcid'], pair['cited_pmcid']
        ca, da = articles[cid], articles[did]
        key = pair['candidate_id']
        if 'pdf_source' not in ca or 'pdf_source' not in da:
            failures.append({'candidate_pair': key, 'status': 'main_pdf_missing_before_case_freeze',
                             'citing_pmcid': cid, 'cited_pmcid': did,
                             'note': 'No supplement PDF substituted for main article; not an inference result or semantic exclusion.'})
            continue
        try:
            cd, dd = load_pdf(ca), load_pdf(da)
            overlap = (cd['sha256'], dd['sha256']) in legacy_pairs or (cid, did) in legacy_pmcpairs
            if overlap:
                raise ValueError('Known route2 shared paper-pair overlap; exclude from independent route1 batch')
            xml = ET.parse(ca['xml_source']['path']).getroot()
            parents = {child: parent for parent in xml.iter() for child in parent}
            ref_id = pair['citing_xml_locator'].split('bibliography_xref=')[1].split(';')[0]
            ref = next(r for r in xml.iter('ref') if r.get('id') == ref_id)
            ref_dois = [x.text or '' for x in ref.iter('pub-id') if x.get('pub-id-type') == 'doi']
            ref_dois += [x.get('{http://www.w3.org/1999/xlink}href', '') for x in ref.iter('ext-link') if x.get('ext-link-type') == 'doi']
            assert any(canon(x) == canon(da['doi']) for x in ref_dois), 'Bibliography DOI does not match cited PDF'
            ref_pmcids = [x.text or '' for x in ref.iter('pub-id') if x.get('pub-id-type') == 'pmcid']
            ref_pmcids += [x.get('{http://www.w3.org/1999/xlink}href', '') for x in ref.iter('ext-link') if x.get('ext-link-type') == 'pmcid']
            assert did in ref_pmcids, 'Bibliography PMCID does not match cited PDF'
            title = canon(da['title'])
            title_pos = cd['canonical'].find(title)
            assert title_pos >= 0 and cd['canonical'].count(title) == 1, 'Unique cited title in citing PDF reference not located'
            ref_loc = raw_fragments(cd, [(cd['canonical_mapping'][title_pos], cd['canonical_mapping'][title_pos + len(title) - 1] + 1)])
            pair_id = 'r1pair:' + digest_text(cd['sha256'] + '|' + dd['sha256'])[:20]
            xs = [x for x in xml.iter('xref') if ref_id in x.get('rid', '').split()]
            good = []
            for ordinal, x in enumerate(xs, 1):
                try:
                    paragraph = x
                    while paragraph in parents and paragraph.tag != 'p':
                        paragraph = parents[paragraph]
                    assert paragraph.tag == 'p', 'Reference occurrence has no prose paragraph'
                    context, marker, notes, xml_marker, xml_text, scope = paragraph_location(cd, paragraph, x)
                    citation_group = full_numeric_citation_group(cd, marker)
                    payload = {'citing_pdf_sha256': cd['sha256'], 'marker_locations': [
                        {k: f[k] for k in ['pdf_page', 'char_start', 'char_end_exclusive']} for f in marker],
                               'cited_pdf_sha256': dd['sha256']}
                    full_key = digest_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
                    case_id = 'r1pdf:' + full_key[:24]
                    raw_context = '\n'.join(f['raw_text'] for f in context)
                    row = {'case_id': case_id, 'route': 'route1', 'domain': 'biomedicine',
                           'domain_basis': 'citing-paper biomedical/protein subject matter, assigned before any new model prediction',
                           'pair_id': pair_id, 'dedup_key': full_key, 'dedup_key_payload': payload,
                           'source_pool_candidate_id': key, 'reference_id': ref_id, 'xml_occurrence_ordinal': ordinal,
                           'citing_pmcid': cid, 'cited_pmcid': did, 'citation_marker_xml_helper': xml_marker,
                           'citation_marker_pdf_raw': [f['raw_text'] for f in marker],
                           'citation_group_pdf_raw': [f['raw_text'] for f in citation_group],
                           'citation_group_locator': citation_group,
                           'citation_group_scope_note': 'Target reference is one member of the retained printed group; no fabricated isolated reference or automatic assignment of the entire group claim to one article.',
                           'citing_context_raw_fragments': context, 'citation_marker_locator': marker,
                           'citing_context': normalized_pdf_text(raw_context),
                           'citing_context_marked': mark_target(context, marker),
                           'target_claim_scope_proposal': normalized_pdf_text('\n'.join(f['raw_text'] for f in scope)),
                           'target_claim_scope_pdf_fragments': scope,
                           'target_scope_review_status': 'automatic_sentence_proposal_pending_human_review; original_full_paragraph_retained',
                           'context_normalization': 'NFKC; discretionary/Latin line-wrap hyphen normalization; whitespace collapse. Raw PDF fragments retained unchanged.',
                           'context_scope': 'complete source paragraph matched via XML helper; repeated layout material omitted explicitly, claim words not rewritten',
                           'xml_helper_paragraph_sha256': digest_text(xml_text), 'xml_pdf_alignment_notes': notes,
                           'reference_pdf_title_locator': ref_loc,
                           'source_identity_check': 'XML reference DOI and PMCID match cited metadata; unique cited title located in citing PDF; both PDF title/DOI verified',
                           'shared_route2_sample_overlap': False,
                           'route2_overlap_audit_scope': 'known five shared pairs / ten retained citation points, not an assertion of complete graph-node disjointness',
                           'shared_citing_article_with_legacy_route2_points': cid == 'PMC11350039',
                           'classifier_preselected': {'name': 'Mbio', 'checkpoint': 'checkpoint-100',
                                'adapter_sha256_expected': '0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09',
                                'base_revision_expected': '1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0', 'reasoning': False},
                           'classification_performed': False, 'model_prediction': None,
                           'classifier_actual_run': None, 'explanation_actual_run': None,
                           'selected_evidence_ids': [], 'evidence_status': 'awaiting_cited_pdf_retrieval',
                           'reason': None, 'confidence': None, 'confidence_status': 'uncalibrated',
                           'reviewers': {'李云': {'label': None, 'reason': None, 'prediction_exposure': None, 'reviewed_at': None},
                                         '陈明进': {'label': None, 'reason': None, 'prediction_exposure': None, 'reviewed_at': None}},
                           'prior_annotation_exposure_note': 'Existing route1 natural-candidate material may have prior judgments. No independent blindness is claimed for this prepared batch.',
                           'adjudicated_label': None, 'engineering_status': 'not_run',
                           'locator_review_status': 'machine_replayed_pending_human_review',
                           'explanation_semantic_status': 'not_run', 'end_to_end_accepted': False}
                    good.append(row)
                except Exception as exc:
                    failures.append({'candidate_pair': key, 'reference_id': ref_id, 'xml_occurrence_ordinal': ordinal,
                                     'status': 'PDF_context_or_marker_localization_pending', 'detail': str(exc),
                                     'not_a_semantic_or_prediction_based_exclusion': True})
            good.sort(key=lambda r: [(f['pdf_page'], f['char_start']) for f in r['citation_marker_locator']])
            prepared[key] = good
            pair_rows.append({'pair_id': pair_id, 'source_pool_candidate_id': key,
                              'citing': {'pmcid': cid, 'title': ca['title'], 'doi': ca['doi'], **ca['pdf_source']},
                              'cited': {'pmcid': did, 'title': da['title'], 'doi': da['doi'], **da['pdf_source']},
                              'citing_xml_helper': ca['xml_source'],
                              'reference_id': ref_id, 'reference_pdf_title_locator': ref_loc,
                              'license_codes': {'citing': ca.get('license_code'), 'cited': da.get('license_code')},
                              'identity_checks': {'citing': cd['identity_checks'], 'cited': dd['identity_checks']},
                              'prepared_points': len(good), 'known_route2_shared_pair_overlap': False})
        except Exception as exc:
            failures.append({'candidate_pair': key, 'status': 'pair_identity_or_source_check_pending', 'detail': str(exc)})
    selected, reserves = [], []
    for round_no in range(max((len(v) for v in prepared.values()), default=0)):
        for values in prepared.values():
            if round_no < len(values):
                (selected if len(selected) < 20 else reserves).append(values[round_no])
    all_points = selected + reserves
    assert len({r['dedup_key'] for r in all_points}) == len(all_points), 'Duplicate physical citation point'
    for r in selected:
        r['sample_set'] = 'route1_pdf20_source_scope_v1'
        r['source_scope_locked_before_new_inference'] = True
        r['location_applicability_precheck'] = 'text_layer_both_PDFs_and_marker_position_available; human audit pending'
    for r in reserves:
        r['sample_set'] = 'unselected_reserve_not_additional_completed_cases'
    selected_counts = collections.Counter(r['pair_id'] for r in selected)
    for r in pair_rows:
        r['selected_points'] = selected_counts[r['pair_id']]
    rows(BASE / 'case_manifest.jsonl', selected)
    rows(BASE / 'pair_manifest.jsonl', pair_rows)
    rows(BASE / 'reserve_case_manifest.jsonl', reserves)
    rows(BASE / 'source_or_location_pending.jsonl', failures)
    requests = [{'case_id': r['case_id'], 'pair_id': r['pair_id'], 'route': 'route1',
                 'citing_context': r['citing_context'], 'citing_context_marked': r['citing_context_marked'],
                 'target_claim_scope_proposal': r['target_claim_scope_proposal'],
                 'target_scope_review_status': r['target_scope_review_status'],
                 'citation_marker_pdf_raw': r['citation_marker_pdf_raw'],
                 'citation_group_pdf_raw': r['citation_group_pdf_raw'],
                 'target_reference_id': r['reference_id'],
                 'cited_pdf': next(p['cited'] for p in pair_rows if p['pair_id'] == r['pair_id']),
                 'retrieval_scope': 'this cited PDF only', 'retrieval_config_status': 'to_be_fixed_by_cited_side_before_first_run',
                 'candidates': None, 'retrieval_performed': False} for r in selected]
    rows(BASE / 'cited_retrieval_requests.jsonl', requests)
    dump(BASE / 'route2_overlap_audit.json', {'legacy_source': str(legacy), 'legacy_source_sha256': sha(legacy),
        'legacy_pairs': len(legacy_pairs), 'legacy_points': len(old_points),
        'comparison': 'both PDF hashes or PMCID pair identity; thus different markers in known shared pair are conservatively excluded here',
        'new_selected_pair_overlap_count': 0,
        'shared_citing_article_is_not_same_citation_point': True,
        'complete_116_edge_graph_crosswalk_performed': False,
        'new_cases_not_claimed_to_be_blind_annotations': True})
    summary = {'date': '2026-10-20', 'stage': 'source_scope_and_citing_locations_only',
               'freeze_status': 'source_scope_locked_before_new_inference' if len(selected) == 20 and len(selected_counts) >= 5 else 'provisional_scale_shortfall',
               'selected_points': len(selected), 'selected_pairs': len(selected_counts),
               'distinct_citing_articles': len({r['citing_pmcid'] for r in selected}),
               'distinct_cited_articles': len({r['cited_pmcid'] for r in selected}),
               'all_prepared_points': len(all_points), 'reserve_points': len(reserves),
               'source_or_location_pending_records': len(failures),
               'known_route2_shared_pair_overlap': 0, 'new_classifier_runs': 0,
               'engineering_successes': 0, 'human_confirmed_locator_valid': None,
               'explanation_passes': 0, 'adjudicated_classification_correct': None,
               'adjudicated_labels': 0, 'formal_location_validity_rate': None,
               'meaning': 'Sources and physical citation locations locked; this is not 20 completed/qualified points and not a 100% validity result.',
               'expected_final_locator_denominator': 20, 'minimum_valid_for_80_percent': 16,
               'no_silent_subset_denominator': True, 'models_or_gold_modified': False,
               'extractor': {'name': 'PyMuPDF', 'version': fitz.VersionBind},
               'source_files_manifest': 'SHA256SUMS.json'}
    dump(BASE / 'preparation_summary.json', summary)
    dump(BASE / 'source_acquisition_with_existing_reuse.json', {'articles': list(articles.values())})
    frozen = {'case_manifest.jsonl': sha(BASE / 'case_manifest.jsonl'),
              'pair_manifest.jsonl': sha(BASE / 'pair_manifest.jsonl'),
              'selection_policy_v2_before_new_inference.json': sha(pp),
              'cited_retrieval_requests.jsonl': sha(BASE / 'cited_retrieval_requests.jsonl')}
    dump(BASE / 'scope_lock.json', {'date': '2026-10-20', 'case_count': len(selected),
                                   'phase': 'before any new classifier inference on this batch',
                                   'files_sha256': frozen, 'human_joint_signoff': False})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for p in pair_rows:
        print(p['source_pool_candidate_id'], p['citing']['pmcid'], '->', p['cited']['pmcid'],
              'prepared=', p['prepared_points'], 'selected=', p['selected_points'])
    print('PENDING', json.dumps(failures, ensure_ascii=False))


if __name__ == '__main__':
    main()
