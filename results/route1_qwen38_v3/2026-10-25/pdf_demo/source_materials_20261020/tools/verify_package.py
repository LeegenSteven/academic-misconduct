"""Standard-library read-only verification of a received source-scope package."""
from pathlib import Path
import hashlib
import json

BASE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((BASE / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    for relative, expected in manifest['files'].items():
        path = (BASE / relative).resolve()
        if not path.is_relative_to(BASE.resolve()):
            raise ValueError('Unsafe package path')
        assert path.is_file(), ('Missing file', relative)
        assert path.stat().st_size == expected['bytes'], ('File size mismatch', relative)
        assert sha(path) == expected['sha256'], ('File hash mismatch', relative)
    frozen = json.loads((BASE / 'scope_lock.json').read_text(encoding='utf-8'))
    for relative, expected in frozen['files_sha256'].items():
        assert sha(BASE / relative) == expected, ('Scope lock mismatch', relative)
    cases = [json.loads(x) for x in (BASE / 'case_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(cases) == 20 and len({r['dedup_key'] for r in cases}) == 20
    assert len({r['pair_id'] for r in cases}) == 10
    assert all(not r['classification_performed'] and r['adjudicated_label'] is None for r in cases)
    print('PACKAGE_INTEGRITY_PASS; cases=20; pairs=10; new_model_runs=0')
    print('This verifies files and source-scope records, not semantic acceptance or independent human agreement.')


if __name__ == '__main__':
    main()
