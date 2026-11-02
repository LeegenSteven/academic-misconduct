"""Package sources and preparation records, then verify a fresh extracted copy."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
ARCHIVE = BASE.parent / '路线一PDF20点_来源与被引检索交接_20261020.zip'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = sorted(p for p in BASE.rglob('*') if p.is_file()
                   and 'history' not in p.relative_to(BASE).parts
                   and '__pycache__' not in p.relative_to(BASE).parts
                   and p.name != 'SHA256SUMS.json')
    entries = {p.relative_to(BASE).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files}
    manifest = {'date': '2026-10-20', 'files': entries,
                'meaning': 'File integrity and fixed source-scope records only; not semantic acceptance.'}
    (BASE / 'SHA256SUMS.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    subprocess.run([sys.executable, str(BASE / 'tools/verify_package.py')], check=True)
    with zipfile.ZipFile(ARCHIVE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files + [BASE / 'SHA256SUMS.json']:
            z.write(p, p.relative_to(BASE).as_posix())
    with zipfile.ZipFile(ARCHIVE) as z:
        names = z.namelist()
        assert len(names) == len(set(names)) == len(entries) + 1
        assert z.testzip() is None
        for name, expected in entries.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == expected['sha256']
        # A new inspection directory; no original directory is moved or deleted.
        extracted = (ROOT / 'tmp/route1_pdf20_source_package_check_20261020').resolve()
        assert extracted.is_relative_to((ROOT / 'tmp').resolve())
        for name in names:
            assert (extracted / name).resolve().is_relative_to(extracted)
        extracted.mkdir(parents=True, exist_ok=True)
        for name in names:
            dest = extracted / name
            data = z.read(name)
            if dest.exists():
                assert dest.read_bytes() == data, ('Existing inspection copy differs', name)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
    subprocess.run([sys.executable, str(extracted / 'tools/verify_package.py')], check=True)
    summary = json.loads((BASE / 'preparation_summary.json').read_text(encoding='utf-8'))
    receipt = {'date': '2026-10-20', 'archive': str(ARCHIVE), 'archive_sha256': sha(ARCHIVE),
               'archive_bytes': ARCHIVE.stat().st_size, 'archive_files': len(entries) + 1,
               'source_scope_folder': str(BASE), 'selected_pairs': summary['selected_pairs'],
               'selected_points': summary['selected_points'], 'reserve_points': summary['reserve_points'],
               'known_shared_route2_overlap': 0, 'source_character_replay_checked': 20,
               'visual_marker_previews_assisted_reviewed': 20,
               'fresh_extracted_copy_standard_library_verification': 'PASS',
               'meaning': 'Preparation-file integrity only; no model inference or final acceptance.',
               'next_step': 'Cited-side source/scope review and fixed retrieval; citing-side unified entry in parallel.',
               'new_classifier_runs': 0, 'engineering_successes': 0, 'formal_locator_validity': None,
               'human_joint_scope_signoff': False, 'outgoing_message_sent': False}
    receipt_path = BASE.parent / '路线一PDF20点_交接包核验_20261020.json'
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
