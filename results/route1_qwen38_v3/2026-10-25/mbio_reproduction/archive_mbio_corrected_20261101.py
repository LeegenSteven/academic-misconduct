"""Archive an existing Mbio run on A100, or verify its downloaded archive. No model run."""
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import tarfile
import uuid

RUN = Path('/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_corrected_20261031')
REPO = Path('/home/admire/academic-misconduct-route1')
ARCHIVE = Path('/home/admire/mbio_corrected_ckpt134_handoff_20261101.tar.gz')
EXPECTED = {
    'train/training_config.json': '24d8251ae7a896079c69962b3b7b335fb7856fc743a8353f6fdb876068de9584',
    'test/sarol/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_metrics.json': 'bc2a6a917de71b9202d452f5154cd2b102e699e8bfa6e602d89c6469dbe50bf0',
    'test/sarol/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_predictions.jsonl': '0416472fece95f94ebe6a86047d38fdafffd6376adfbf2918c2b6f22054b84b6',
    'test/sciciteval/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_metrics.json': '587a1be67b11e5f6027bf241b43c45f3d43c8a36ae72b3e17959fb3eb8508009',
    'test/sciciteval/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_predictions.jsonl': '1c404f5a6cdc007d351cc70dad0c6427061bb78e9e0f5c5fefa24e4bb38677d2',
    'source/code/cmj/route1_qwen38_train_sarol_memopt_v1.py': '9a47a2daa2c92b19d6274e26b526075a5402406e3de068852585ff32818e4aba',
}
DEV_PREDICTIONS = {
    'dev_selection/checkpoint-100/Mbio_corrected_ckpt100_dev_predictions.jsonl': '5918c9042c5ff7760fe6f39c5155488500df08ba7c4aaa2109d9f2bfff53b127',
    'dev_selection/checkpoint-134/Mbio_corrected_ckpt134_dev_predictions.jsonl': 'cad9c96c4355e1c174934a7440f0c7f44bbf3129caa73312f3da6a455e0336ff',
}
EXPECTED.update(DEV_PREDICTIONS)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha_stream(stream):
    h = hashlib.sha256()
    while data := stream.read(8 * 1024 * 1024):
        h.update(data)
    return h.hexdigest()


def sha_file(path):
    with path.open('rb') as stream:
        return sha_stream(stream)


def identity(path):
    require(path.is_file(), f'Missing required file: {path}')
    stat = path.stat()
    require(stat.st_size > 0, f'Empty required file: {path}')
    return {'path_on_a100': str(path), 'bytes': stat.st_size, 'sha256': sha_file(path)}


def payload_sources():
    files = {'run/' + name: RUN.parent / (RUN.name + suffix) for name, suffix in (
        ('train.log', '.train.log'),
        ('dev_selection.run.log', '.dev_selection.run.log'),
        ('test.run.log', '.test.run.log'),
    )}
    files['train/training_config.json'] = RUN / 'train/training_config.json'
    for name in ('adapter_config.json', 'adapter_model.safetensors', 'chat_template.jinja', 'tokenizer_config.json', 'tokenizer.json', 'README.md', 'trainer_state.json', 'training_args.bin'):
        key = 'train/checkpoint-134/' + name
        files[key] = RUN / key
    for name in ('adapter_config.json', 'trainer_state.json'):
        key = 'train/checkpoint-100/' + name
        files[key] = RUN / key
    for n in (100, 134):
        for ext in ('metrics.json', 'predictions.jsonl'):
            key = f'dev_selection/checkpoint-{n}/Mbio_corrected_ckpt{n}_dev_{ext}'
            files[key] = RUN / key
    for domain in ('sarol', 'sciciteval'):
        for ext in ('metrics.json', 'predictions.jsonl'):
            key = f'test/{domain}/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_{ext}'
            files[key] = RUN / key
    for rel in ('code/cmj/route1_qwen38_train_sarol_memopt_v1.py', 'code/cmj/route1_qwen38_eval_v1.py', 'code/shared/route1_qwen38/data_contract.py'):
        files['source/' + rel] = REPO / rel
    return files


def validate_records(name, data):
    if not name.endswith('_predictions.jsonl'):
        return
    rows = [json.loads(line) for line in data.decode('utf-8-sig').splitlines() if line.strip()]
    expected = 316 if name.startswith('dev_selection/') else (606 if name.startswith('test/sarol/') else 257)
    require(len(rows) == expected, f'Prediction count differs: {name}')
    require(len({str(r['claim_id']) for r in rows}) == expected, f'Duplicate IDs: {name}')


def verify(path, expected_archive_sha=None):
    require(path.is_file(), f'Archive not found: {path}')
    checksum_path = Path(str(path) + '.sha256')
    if expected_archive_sha is None:
        require(checksum_path.is_file(), f'Checksum not found: {checksum_path}')
        expected_archive_sha = checksum_path.read_text(encoding='utf-8-sig').split()[0].lower()
    require(re.fullmatch('[0-9a-f]{64}', expected_archive_sha), 'Malformed archive SHA256')
    actual_sha = sha_file(path)
    require(actual_sha == expected_archive_sha, 'Downloaded archive SHA256 mismatch')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        require(len(names) == len(set(names)), 'Duplicate archive member names')
        for member in members:
            parts = PurePosixPath(member.name)
            require(member.isfile() and not parts.is_absolute() and '..' not in parts.parts and '\\' not in member.name, 'Unsafe archive member')
        require('manifest.json' in names, 'Missing manifest')
        manifest = json.load(archive.extractfile('manifest.json'))
        entries = manifest['payload']
        require(set(names) == set(entries) | {'manifest.json'}, 'Archive payload list differs')
        for name, info in entries.items():
            member = archive.getmember(name)
            require(member.size == info['bytes'], f'Size mismatch: {name}')
            with archive.extractfile(member) as stream:
                actual = sha_stream(stream)
            require(actual == info['sha256'], f'Payload SHA256 mismatch: {name}')
            if name in EXPECTED:
                require(actual == EXPECTED[name], f'Previous A100 SHA256 mismatch: {name}')
            if name.endswith('_predictions.jsonl'):
                validate_records(name, archive.extractfile(member).read())
        require(set(EXPECTED).issubset(entries), 'Missing fixed evidence')
        adapter_hash = entries['train/checkpoint-134/adapter_model.safetensors']['sha256']
    print('ARCHIVE_AND_PAYLOAD_SHA256_OK')
    print(f'payload_files={len(entries)} dev_predictions=316+316 test_predictions=606+257')
    print(f'checkpoint134_weight_sha256={adapter_hash}')
    print(f'archive_sha256={actual_sha}')
    print('model_loaded=false inference_performed=false human_acceptance_inferred=false')


def pack():
    require(sys.platform.startswith('linux'), '--pack must run on A100 Linux; use --verify on Windows')
    if ARCHIVE.exists():
        verify(ARCHIVE)
        print(f'EXISTING_ARCHIVE_VERIFIED_NOT_OVERWRITTEN={ARCHIVE}')
        return
    checksum_path = Path(str(ARCHIVE) + '.sha256')
    require(not checksum_path.exists(), f'Checksum already exists without archive: {checksum_path}')
    files = payload_sources()
    metadata = {}
    for name, path in files.items():
        metadata[name] = identity(path)
        if name in EXPECTED:
            require(metadata[name]['sha256'] == EXPECTED[name], f'Frozen/report SHA256 mismatch: {path}')
        if name.endswith('_predictions.jsonl'):
            validate_records(name, path.read_bytes())
    external = {}
    for ckpt in ('checkpoint-100', 'final_adapter'):
        for name in ('adapter_config.json', 'adapter_model.safetensors'):
            rel = f'train/{ckpt}/{name}'
            external[rel] = identity(RUN / rel)
    manifest = {
        'version': 'mbio_corrected_ckpt134_handoff_20261101',
        'source_run': str(RUN),
        'selected_checkpoint': 'checkpoint-134',
        'selection_rule': 'Sarol Dev Macro-F1',
        'payload': metadata,
        'hash_only_sources_not_in_payload': external,
        'runtime_at_archiving_not_training': {
            'python': platform.python_version(),
            'packages': {n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'peft', 'accelerate', 'bitsandbytes', 'datasets')},
        },
        'script_sha256': sha_file(Path(__file__)),
        'old_history_overwritten': False,
        'model_loaded': False,
        'inference_performed': False,
        'scope': 'Archive/checksum validation only; no semantic acceptance or new model run.',
        'source_snapshot_scope': 'Source files and installed package versions captured at archiving time; original execution logs remain the run evidence.',
    }
    tmp = ARCHIVE.with_name(ARCHIVE.name + '.partial-' + uuid.uuid4().hex)
    try:
        with tarfile.open(tmp, 'x:gz', compresslevel=1) as archive:
            for name, path in files.items():
                archive.add(path, arcname=name, recursive=False)
            raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            entry = tarfile.TarInfo('manifest.json')
            entry.size = len(raw)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(raw))
        package_sha = sha_file(tmp)
        verify(tmp, package_sha)
        require(not ARCHIVE.exists(), 'Archive appeared while packing; do not overwrite')
        # Linux hard-link publishes the complete package exclusively, never overwriting.
        os.link(tmp, ARCHIVE)
        with checksum_path.open('x', encoding='utf-8') as stream:
            stream.write(f'{package_sha}  {ARCHIVE.name}\n')
    finally:
        if tmp.exists():
            tmp.unlink()
    print(f'PACKED={ARCHIVE}')
    print(f'CHECKSUM={checksum_path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pack', action='store_true')
    mode.add_argument('--verify', type=Path, metavar='TAR_GZ')
    args = parser.parse_args()
    if args.pack:
        pack()
    else:
        verify(args.verify)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ARCHIVE_CHECK_FAILED {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
