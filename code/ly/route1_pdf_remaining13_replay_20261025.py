"""Replay the frozen 13-point resource variant with truthful operator/new paths.

This driver requires the unchanged 2026-10-24 resource package. It changes only
the execution identity and launch/output bookkeeping. Original generation,
resource policy, release verification and strict parser remain in that package.
No model is imported by --verify-only, --self-check or --preflight.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import types
import zipfile

VERSION = 'route1_pdf_remaining13_replay_20261025'
PACKAGE_SHA = '4b21f1269bd808491cdcaf9d67ef82a2c706997ae39ed42079c1c4dc4444e66b'
MAIN_SHA = '166f9c1db0f2553b62e0d51d12e8f95bb016a810384954cf1759fda20c685182'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load_frozen_driver(package):
    require(sha(package) == PACKAGE_SHA, 'Original resource package differs')
    with zipfile.ZipFile(package) as archive:
        raw = archive.read('__main__.py')
    require(hashlib.sha256(raw).hexdigest() == MAIN_SHA, 'Original driver differs')
    module = types.ModuleType('_route1_frozen_resource_driver')
    module.__file__ = str(package) + '/__main__.py'
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    policy, expected = module.own_files(package)

    # Exactly two original operator constants occur inside run(): the request
    # record and HFBackend constructor. Do not change any generation call.
    tree = ast.parse(raw)
    original_run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    patched_run = copy.deepcopy(original_run)

    class OperatorOnly(ast.NodeTransformer):
        changed = 0

        def visit_Constant(self, node):
            if node.value == '李云':
                self.changed += 1
                return ast.copy_location(ast.Attribute(value=ast.Name(id='args', ctx=ast.Load()), attr='operator', ctx=ast.Load()), node)
            return node

    patcher = OperatorOnly()
    patched_run = patcher.visit(patched_run)
    require(patcher.changed == 2, 'Expected exactly two operator substitutions')
    ast.fix_missing_locations(patched_run)

    # Roundtrip the patch and prove the complete function is otherwise equal.
    reverted = copy.deepcopy(patched_run)

    class UndoOperator(ast.NodeTransformer):
        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'args' and node.attr == 'operator':
                return ast.copy_location(ast.Constant(value='李云'), node)
            return self.generic_visit(node)

    reverted = UndoOperator().visit(reverted)
    require(ast.dump(reverted, include_attributes=False) == ast.dump(original_run, include_attributes=False), 'Unexpected execution change')
    patched_module = ast.Module(body=[patched_run], type_ignores=[])
    ast.fix_missing_locations(patched_module)
    exec(compile(patched_module, str(Path(__file__).resolve()) + '[operator-only]', 'exec'), module.__dict__)
    module.VERSION = VERSION
    module.replay_effective_run_source = ast.unparse(patched_run) + '\n'
    return module, policy, expected


def stage_args(args, stage):
    result = copy.copy(args)
    result.stage = stage
    result.adapter = args.adapter if stage == 'classifier' else None
    return result


def selected_stages(args):
    return ('classifier', 'explainer') if args.stage == 'both' else (args.stage,)


def launch_paths(args):
    log = args.output_root.with_name(args.output_root.name + '.run.log')
    receipt = args.output_root.with_name(args.output_root.name + '.launch.json')
    return log, receipt


def preflight(args, module, expected):
    require(args.operator is not None and args.operator.strip(), 'Supply the actual executor with --operator')
    require(args.operator == args.operator.strip(), 'Operator must not have leading/trailing spaces')
    require(not any(c in args.operator for c in '\r\n\x00'), 'Invalid operator text')
    require(args.output_root is not None, 'A new --output-root is required')
    require(args.gpu.isdecimal() and args.gpu.isascii(), 'Select one physical GPU index')
    args.output_root = args.output_root.resolve()
    require(not args.output_root.exists(), 'Output root already exists; preserve the prior run')
    for protected in (args.root, args.source_root, args.prepared_dir, args.model_path, args.adapter, args.release.parent):
        require(not args.output_root.is_relative_to(protected.resolve()), 'Output must be outside frozen sources/model/adapter/release')
    for path in (args.source_root, args.prepared_dir, args.model_path, args.pymupdf_dir, args.adapter):
        require(path.is_dir(), 'Required directory missing: ' + str(path))
    require(args.weights_manifest.is_file(), 'Weights manifest missing')
    for stage in selected_stages(args):
        module.verify_server(stage_args(args, stage), expected)
    log, receipt = launch_paths(args)
    if args.launch:
        require(not log.exists() and not receipt.exists(), 'Replay log/receipt already exists; use a new output root')
    require('torch' not in sys.modules, 'Preflight unexpectedly imported torch')
    return {'status': 'REPLAY_CODE_AND_RELEASE_PREFLIGHT_PASS_NO_MODEL_RUN',
            'version': VERSION, 'operator_as_entered': args.operator,
            'operator_identity_independently_authenticated': False,
            'selected_points': 13, 'fixed_denominator': 20,
            'stages': list(selected_stages(args)), 'release_sha256': sha(args.release),
            'original_package_sha256': PACKAGE_SHA, 'replay_driver_sha256': sha(__file__),
            'output_root': str(args.output_root), 'model_loaded': False, 'GPU_used': False,
            'scope': 'Code/release/path checks only. Actual backend retains weight, environment and token checks.'}


def command_for(args, stage=None, output_root=None):
    # Explicit arguments keep the child bound to the same original files.
    command = [sys.executable, '-u', str(Path(__file__).resolve()), '--run',
               '--package', str(args.package), '--operator', args.operator,
               '--stage', stage or args.stage, '--gpu', args.gpu]
    for option in ('root', 'release', 'source_root', 'prepared_dir', 'output_root',
                   'model_path', 'weights_manifest', 'pymupdf_dir', 'adapter'):
        value = output_root if option == 'output_root' and output_root is not None else getattr(args, option)
        command.extend(['--' + option.replace('_', '-'), str(value)])
    return command


def launch(args):
    require(os.name == 'posix', 'Launch this driver on the A100 Linux host')
    log, receipt = launch_paths(args)
    log.parent.mkdir(parents=True, exist_ok=True)
    command = ['nohup'] + command_for(args)
    with log.open('xb') as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    write_new(receipt, {'version': VERSION, 'created_at_utc': now(), 'pid': process.pid,
                        'operator_as_entered': args.operator, 'command': command,
                        'replay_driver_sha256': sha(__file__), 'original_package_sha256': PACKAGE_SHA,
                        'log': str(log), 'completed': False})
    print('REPLAY_PID=' + str(process.pid), flush=True)
    print('RUN_LOG=' + str(log), flush=True)
    print('OUTPUT_ROOT=' + str(args.output_root), flush=True)


def run(args, module, policy, expected):
    require(os.name == 'posix', 'Run this driver on the A100 Linux host')
    args.output_root.mkdir(parents=True, exist_ok=False)
    driver_copy = args.output_root / 'replay_driver.py.txt'
    with driver_copy.open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    with (args.output_root / 'effective_original_run.py.txt').open('x', encoding='utf-8') as stream:
        stream.write(module.replay_effective_run_source)
    write_new(args.output_root / 'replay_request.json', {
        'version': VERSION, 'started_at_utc': now(), 'operator_as_entered': args.operator,
        'operator_identity_independently_authenticated': False,
        'original_package_sha256': PACKAGE_SHA, 'original_main_sha256': MAIN_SHA,
        'replay_driver_sha256': sha(driver_copy), 'release_sha256': sha(args.release),
        'selected_points': 13, 'fixed_denominator': 20, 'stages': list(selected_stages(args)),
        'execution_change': 'Actual operator replaces two old hardcoded constants; unique launch/output paths and replay provenance added.',
        'generation_resource_parser_unchanged': True,
        'point16_compact_v2_not_replayed': True,
        'classification_Test_run': False, 'training_run': False, 'new_human_judgments': 0,
        'independent_reviewer_signoff_inferred': False,
    })
    outcomes = []
    code = 1
    failure = None
    try:
        for stage in selected_stages(args):
            print('REPLAY_STAGE_START role=' + stage, flush=True)
            if args.stage == 'both':
                # Each model role gets its own process. GPU memory and imported
                # backend state do not carry from classifier into explainer.
                child_root = args.output_root / (stage + '_execution')
                child_log = args.output_root / (stage + '.run.log')
                with child_log.open('xb') as stream:
                    code = subprocess.run(command_for(args, stage=stage, output_root=child_root),
                                          stdin=subprocess.DEVNULL, stdout=stream,
                                          stderr=subprocess.STDOUT, check=False).returncode
                outcomes.append({'stage': stage, 'exit_code': code,
                                 'child_root': str(child_root), 'log': str(child_log),
                                 'actual_stage_output': str(child_root / stage)})
            else:
                code = module.run(stage_args(args, stage), args.package, policy, expected)
                outcomes.append({'stage': stage, 'exit_code': code,
                                 'actual_stage_output': str(args.output_root / stage)})
            print('REPLAY_STAGE_END role=' + stage + ' exit_code=' + str(code), flush=True)
            if code != 0:
                break
        return code
    except Exception as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        write_new(args.output_root / 'replay_summary.json', {
            'version': VERSION, 'finished_at_utc': now(), 'operator_as_entered': args.operator,
            'status': 'STAGES_COLLECTED_NOT_ENGINEERING_OR_HUMAN_ACCEPTANCE' if code == 0 and failure is None else 'EXECUTION_FAILED_OR_INCOMPLETE',
            'stages': outcomes, 'exception': failure, 'fixed_denominator': 20,
            'selected_points': 13, 'formal_acceptance_added': 0,
            'independent_identity_or_signoff_verified': False,
        })


def self_check(module):
    sample = argparse.Namespace(stage='both', adapter=Path('/frozen/adapter'), output_root=Path('/tmp/new_replay'))
    require(stage_args(sample, 'classifier').adapter == sample.adapter, 'Classifier adapter lost')
    require(stage_args(sample, 'explainer').adapter is None, 'Explainer received adapter')
    require(selected_stages(sample) == ('classifier', 'explainer'), 'Stage order changed')
    log, receipt = launch_paths(sample)
    require(log != receipt and 'run01' not in str(log), 'Old fixed launch path retained')
    require(module.RELEASE_SHA == '09a875e7d8bcae223e39e1ba1c903c99405b17f8c08a8f3797e49dacb01106ec', 'Release identity changed')
    require('args.operator' in module.replay_effective_run_source and '李云' not in module.replay_effective_run_source, 'Operator patch missing')
    require('torch' not in sys.modules, 'Self-check imported torch')
    print('REPLAY_DRIVER_SELF_CHECK_PASS operator_patch=2 adapter_roles=OK new_paths=OK frozen_release=OK model_loaded=false GPU_used=false')


def main():
    home = Path.home()
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    for name in ('verify-only', 'self-check', 'preflight', 'launch', 'run'):
        mode.add_argument('--' + name, action='store_true')
    p.add_argument('--package', type=Path, default=home / 'route1_pdf_remaining13_resource_trial_20261024.pyz')
    p.add_argument('--operator', help='Actual executor, recorded as entered; no identity authentication or signoff implied')
    p.add_argument('--stage', choices=('classifier', 'explainer', 'both'), default='both')
    p.add_argument('--gpu', default='2')
    p.add_argument('--output-root', type=Path)
    p.add_argument('--root', type=Path, default=home / 'route1_pdf_remaining13_r2_20261024')
    p.add_argument('--release', type=Path, default=home / 'route1_pdf_remaining13_r2_release_20261024/release.json')
    p.add_argument('--source-root', type=Path, default=home / 'route1_pdf_cpu_migration_20261021/source')
    p.add_argument('--prepared-dir', type=Path)
    p.add_argument('--model-path', type=Path, default=home / 'route1_pdf_model_view_20261021')
    p.add_argument('--weights-manifest', type=Path, default=home / 'citation_integrity_member2/incoming/quality_v1_20261009/cmj_model_weightcheck_20261016/official_sha256sums.txt')
    p.add_argument('--pymupdf-dir', type=Path, default=home / 'route1_pdf_cpu_deps_20261021')
    p.add_argument('--adapter', type=Path, default=home / 'citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/checkpoint-100')
    args = p.parse_args()
    if args.prepared_dir is None:
        args.prepared_dir = args.root / 'results/route1_qwen38_v3/2026-10-25/pdf_demo/remaining13_preparation_r2_2026-10-24'
    module, policy, expected = load_frozen_driver(args.package)
    if args.verify_only:
        print('REPLAY_DRIVER_VERIFIED original_package=' + PACKAGE_SHA + ' operator_substitutions=2 model_loaded=false GPU_used=false')
        return 0
    if args.self_check:
        self_check(module)
        return 0
    checked = preflight(args, module, expected)
    print(json.dumps(checked, ensure_ascii=False), flush=True)
    if args.preflight:
        return 0
    if args.launch:
        launch(args)
        return 0
    return run(args, module, policy, expected)


if __name__ == '__main__':
    raise SystemExit(main())
