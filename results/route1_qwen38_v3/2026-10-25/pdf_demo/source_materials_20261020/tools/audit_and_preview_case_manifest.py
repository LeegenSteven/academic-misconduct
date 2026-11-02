"""Replay frozen sources and actual PDF character geometry, without inference."""
from pathlib import Path
import collections
import hashlib
import json
import sys

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pdf_locator_deps'))
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(name):
    return [json.loads(x) for x in (BASE / name).read_text(encoding='utf-8').splitlines() if x.strip()]


def main():
    cases, pairs = load_rows('case_manifest.jsonl'), load_rows('pair_manifest.jsonl')
    pairmap = {p['pair_id']: p for p in pairs}
    old = load_rows('history/source_scope_build01_before_target_marking/case_manifest.jsonl')
    assert {r['case_id'] for r in old} == {r['case_id'] for r in cases}, 'Target marking changed selected points'
    assert len(cases) == 20 and len({r['dedup_key'] for r in cases}) == 20
    assert len({r['pair_id'] for r in cases}) >= 5
    output = BASE / 'qa_previews'
    output.mkdir(exist_ok=True)
    replay_checks, previews = [], []
    pdfs = {}
    for p in pairs:
        for role in ['citing', 'cited']:
            source = p[role]
            path = BASE / source['relative_path']
            assert path.is_file() and sha(path) == source['sha256']
            assert path.read_bytes().startswith(b'%PDF-')
            expected_md5 = source.get('official_md5')
            if expected_md5:
                assert hashlib.md5(path.read_bytes()).hexdigest() == expected_md5
            if source['sha256'] not in pdfs:
                pdfs[source['sha256']] = fitz.open(path)
    for ordinal, case in enumerate(cases, 1):
        pair = pairmap[case['pair_id']]
        pdf = pdfs[pair['citing']['sha256']]
        assert case['model_prediction'] is None and not case['classification_performed']
        assert case['adjudicated_label'] is None and not case['end_to_end_accepted']
        assert all(v['label'] is None and v['reviewed_at'] is None for v in case['reviewers'].values())
        payload = {'citing_pdf_sha256': pair['citing']['sha256'],
                   'marker_locations': [{k: f[k] for k in ['pdf_page', 'char_start', 'char_end_exclusive']}
                                        for f in case['citation_marker_locator']],
                   'cited_pdf_sha256': pair['cited']['sha256']}
        h = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert h == case['dedup_key']
        assert case['citing_context_marked'].count('[[TARGET_REFERENCE]]') == len(case['citation_marker_locator'])
        checks = 0
        for group in ['citing_context_raw_fragments', 'citation_marker_locator', 'citation_group_locator', 'target_claim_scope_pdf_fragments', 'reference_pdf_title_locator']:
            values = pair['reference_pdf_title_locator'] if group == 'reference_pdf_title_locator' else case[group]
            for f in values:
                page = pdf[f['pdf_page'] - 1]
                raw = page.get_text('text', sort=False)
                quoted = raw[f['char_start']:f['char_end_exclusive']]
                assert quoted == f['raw_text']
                assert hashlib.sha256(quoted.encode()).hexdigest() == f['raw_text_sha256']
                for block in f['source_blocks']:
                    assert page.rect.contains(fitz.Rect(block['bbox']))
                checks += 1
        # Reconstruct the entire text page from raw character boxes. This also
        # verifies that offsets highlight the actual marker, not another number.
        marker = case['citation_marker_locator'][0]
        page = pdf[marker['pdf_page'] - 1]
        characters, boxes = [], []
        for block in page.get_text('rawdict', sort=False)['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    for char in span['chars']:
                        characters.append(char['c'])
                        boxes.append(char['bbox'])
                characters.append('\n')
                boxes.append(None)
        assert ''.join(characters) == page.get_text('text', sort=False), 'Raw character box/text indexing differs'
        bounds = [fitz.Rect(x) for x in boxes[marker['char_start']:marker['char_end_exclusive']] if x]
        assert bounds
        rect = bounds[0]
        for b in bounds[1:]:
            rect |= b
        clip = fitz.Rect(rect.x0 - 240, rect.y0 - 64, rect.x1 + 240, rect.y1 + 64) & page.rect
        page = pdf[marker['pdf_page'] - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), clip=clip, alpha=False)
        image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(image)
        draw.rectangle([(rect.x0 - clip.x0) * 1.8, (rect.y0 - clip.y0) * 1.8,
                        (rect.x1 - clip.x0) * 1.8, (rect.y1 - clip.y0) * 1.8], outline='#b31919', width=2)
        caption = f'{ordinal:02d}  {case["source_pool_candidate_id"]}   {case["reference_id"]} #{case["xml_occurrence_ordinal"]}  PDF p{marker["pdf_page"]}'
        previews.append((caption, image))
        replay_checks.append({'case_id': case['case_id'], 'source_fragments_replayed': checks,
                              'target_character_geometry_reconstructed': True,
                              'human_semantic_check': False})
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
    for sheet_no in range((len(previews) + 4) // 5):
        canvas = Image.new('RGB', (1120, 1570), 'white')
        draw = ImageDraw.Draw(canvas)
        for index, (caption, image) in enumerate(previews[sheet_no * 5:sheet_no * 5 + 5]):
            y = index * 310
            draw.text((15, y + 8), caption, fill='black', font=font)
            if image.width > 1080:
                image = image.resize((1080, round(image.height * 1080 / image.width)))
            canvas.paste(image, (15, y + 43))
        canvas.save(output / f'marker_review_{sheet_no + 1:02d}.png')
    for pdf in pdfs.values():
        pdf.close()
    report = {'status': 'source_and_character_replay_passed', 'cases': len(cases),
              'pairs': len(pairmap), 'unique_pdf_files_used': len(pdfs),
              'source_set_unchanged_after_target_marking': True,
              'raw_marker_geometry_passed': len(replay_checks), 'checks': replay_checks,
              'formal_validity_rate': None, 'human_review_completed': False,
              'scope_boundary_review_required': True,
              'model_inference_performed': False,
              'meaning': 'Programmatic source identity/offset/character geometry checks, not independent semantic review or final 80% acceptance.'}
    (BASE / 'source_replay_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('SOURCE_AND_CHARACTER_REPLAY_PASS cases=20; points_unchanged=true; previews=4; no_model_run=true')


if __name__ == '__main__':
    main()
