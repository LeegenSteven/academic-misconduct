"""Acquire actual source files for an existing route1 pool; never inspect labels."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
POOL = ROOT / '_route1_test_pair_publish_20261019/data/interim/pmc_oa_expansion_candidate_pool_v1_2026-10-08.json'
CACHE = BASE / 'sources'
LOCK = threading.Lock()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fetch(url: str, destination: Path, md5: str | None = None) -> dict:
    if destination.exists():
        raw = destination.read_bytes()
        if md5 and hashlib.md5(raw).hexdigest() != md5:
            raise ValueError(f'Existing source checksum mismatch: {destination}')
        receipt = destination.with_suffix(destination.suffix + '.receipt.json')
        if not receipt.exists():
            raise ValueError(f'Existing source missing acquisition receipt: {destination}')
        old = json.loads(receipt.read_text(encoding='utf-8'))
        if old['sha256'] != sha(raw) or old['requested_url'] != url:
            raise ValueError(f'Existing source/receipt mismatch: {destination}')
        return old
    attempts = []
    for attempt in range(2):
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'CitationIntegritySourceAudit/1.0'})
            with urllib.request.urlopen(req, timeout=25) as response:
                raw = response.read(85_000_001)
                if len(raw) > 85_000_000:
                    raise ValueError('Source exceeds 85MB bound')
                if md5 and hashlib.md5(raw).hexdigest() != md5:
                    raise ValueError('Official metadata MD5 mismatch')
                receipt = {'requested_url': url, 'final_url': response.url,
                           'retrieved_at_utc': started, 'http_status': response.status,
                           'etag': response.headers.get('ETag'),
                           'last_modified': response.headers.get('Last-Modified'),
                           'sha256': sha(raw), 'bytes': len(raw),
                           'official_md5': md5,
                           'official_md5_verified': bool(md5), 'attempts': attempts}
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            dump(destination.with_suffix(destination.suffix + '.receipt.json'), receipt)
            return receipt
        except Exception as exc:
            attempts.append({'attempt': attempt + 1, 'started_at_utc': started,
                             'error': type(exc).__name__ + ': ' + str(exc)})
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 404):
                break
            if attempt == 0:
                time.sleep(0.3)
    raise RuntimeError(json.dumps({'url': url, 'attempts': attempts}))


def acquire(pmcid: str) -> dict:
    version = pmcid + '.1'
    folder = CACHE / version
    metadata_url = f'https://pmc-oa-opendata.s3.amazonaws.com/{version}/{version}.json'
    entry = {'pmcid': pmcid, 'version': version, 'version_policy': 'explicitly choose version 1; do not claim latest',
             'status': 'not_acquired'}
    try:
        meta_path = folder / (version + '.json')
        fetch(metadata_url, meta_path)
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta['pmcid'] != pmcid or int(meta['version']) != 1:
            raise ValueError('Source identity/version mismatch')
        entry.update({'metadata_path': str(meta_path), 'metadata_sha256': sha(meta_path.read_bytes()),
                      'title': meta['title'], 'doi': meta.get('doi'), 'license_code': meta.get('license_code'),
                      'is_retracted': meta.get('is_retracted'), 'is_manuscript': meta.get('is_manuscript'),
                      'pdf_status': 'not_available_from_main_pdf_url'})
        for field, suffix in [('xml_url', '.xml'), ('pdf_url', '.pdf')]:
            s3url = meta.get(field)
            if not s3url:
                continue
            if not s3url.startswith('s3://pmc-oa-opendata/'):
                raise ValueError('Unexpected source bucket')
            url = s3url.replace('s3://pmc-oa-opendata/', 'https://pmc-oa-opendata.s3.amazonaws.com/', 1)
            md5 = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get('md5', [None])[0]
            path = folder / (version + suffix)
            receipt = fetch(url, path, md5)
            if suffix == '.pdf':
                if not path.read_bytes().startswith(b'%PDF-'):
                    raise ValueError('Main PDF is not a PDF file')
                entry['pdf_status'] = 'main_pdf_acquired_official_md5_verified'
            entry[field.removesuffix('_url') + '_source'] = {'path': str(path), **receipt}
        entry['status'] = 'acquired' if entry.get('xml_source') else 'missing_xml'
    except Exception as exc:
        entry['status'] = 'source_acquisition_failed'
        entry['error'] = str(exc)
    with LOCK:
        print(pmcid, entry['status'], entry.get('pdf_status'), flush=True)
    return entry


def main() -> None:
    raw = POOL.read_bytes()
    pool = json.loads(raw.decode('utf-8-sig'))
    allowed = ['candidate_id', 'citing_pmcid', 'citing_doi', 'citing_title', 'cited_pmcid', 'cited_doi',
               'cited_title', 'citing_xml_locator']
    refs = [{k: r.get(k) for k in allowed} for r in pool['records']]
    policy = {
        'date': '2026-10-20', 'purpose': 'prepare independent route1 real-PDF cases, not new training data',
        'source_pool': str(POOL), 'source_pool_sha256': sha(raw),
        'candidate_pairs': refs,
        'selection_order': 'all existing expansion pool pairs, original candidate_id order; within pair PDF location order',
        'point_selection': 'round robin across valid pairs, 20 points if available; retain all reserves and failures',
        'technical_checks': ['real main PDFs with text layer', 'reference identity', 'exact citation marker in source PDF',
                             'point deduplication', 'route2 shared sample overlap'],
        'forbidden_selection_inputs': ['gold labels', 'model predictions', 'whether a prediction is correct'],
        'new_classifier_predictions_read': False,
        'scope_assignment': 'provisional until source and overlap audit complete',
        'old_five_route2_pairs_kept_separately': True,
    }
    policy_path = BASE / 'selection_policy_before_pdf_processing.json'
    if policy_path.exists():
        assert json.loads(policy_path.read_text(encoding='utf-8')) == policy, 'Do not silently change selection policy'
    else:
        dump(policy_path, policy)
    ids = sorted({r[k] for r in refs for k in ('citing_pmcid', 'cited_pmcid')})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        acquired = list(executor.map(acquire, ids))
    dump(BASE / 'source_acquisition.json', {'date': '2026-10-20', 'records': acquired})
    print('ACQUISITION_DONE', 'articles=', len(acquired),
          'main_pdfs=', sum(bool(r.get('pdf_source')) for r in acquired), flush=True)


if __name__ == '__main__':
    main()
