"""Run the frozen case118 reference in an offline, constrained Docker container."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from .runner import digest, run_trial, ExecutionUncertain
from .validation import validate

REPO = Path(__file__).resolve().parent.parent


def make_request(*, max_iterations=20, timeout_seconds=120):
    if type(max_iterations) is not int or not 0 <= max_iterations <= 1000:
        raise ValueError('max_iterations must be an integer in [0, 1000]')
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 3600:
        raise ValueError('timeout_seconds must be finite in (0, 3600]')
    lock = json.loads((REPO / 'configs/numerical-environment.json').read_text())
    if digest(REPO / 'scripts/reference_pf.m') != lock['reference_script_sha256']:
        raise ValueError('reference script differs from the recorded image')
    if digest(REPO / 'configs/numerical-packages.txt') != lock['package_inventory_sha256']:
        raise ValueError('package inventory differs from the recorded image')
    return dict(policy='fixed-pv-pq-single-slack/1', case='case118',
                case_sha256=lock['case_sha256'], image_id=lock['image_id'],
                environment=lock, max_iterations=max_iterations,
                timeout_seconds=timeout_seconds, validation_tolerance_pu=1e-7,
                source_hashes={name: digest(REPO / 'powerflow_lab' / name)
                               for name in ('validation.py', 'runner.py', 'reference.py')},
                host_python=sys.version, initialization='flat')


def execute_reference(path, request):
    for source, expected in request['source_hashes'].items():
        original = REPO / 'powerflow_lab' / source
        if digest(original) != expected:
            raise ValueError('source changed after request preparation')
        (path / ('source-' + source)).write_bytes(original.read_bytes())
    (path / 'reference_pf.m').write_bytes((REPO / 'scripts/reference_pf.m').read_bytes())
    (path / 'packages.txt').write_bytes((REPO / 'configs/numerical-packages.txt').read_bytes())
    name = 'asr-pf-' + json.loads((path / 'execution.json').read_text())['attempt_id'].lower()
    command = ['docker', 'run', '--name', name, '--label', 'asr.owner=powerflow-lab',
               '--network', 'none', '--read-only', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--pids-limit', '128',
               '--memory', '1g', '--cpus', '1', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m',
               '--user', f'{os.getuid()}:{os.getgid()}', '-e', f"ASR_MAX_IT={request['max_iterations']}",
               '--mount', f'type=bind,src={path.resolve()},dst=/output', request['image_id']]
    status, exit_code = 'failed', None
    with (path / 'solver.log').open('wb') as log:
        try:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=request['timeout_seconds'])
            exit_code = process.returncode
            status = 'succeeded' if exit_code == 0 else 'failed'
        except subprocess.TimeoutExpired:
            status = 'timed_out'
        finally:
            # docker CLI termination alone does not establish container termination.
            try:
                cleanup = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)
                (path / 'cleanup.json').write_text(json.dumps({'returncode': cleanup.returncode,
                                                             'stderr': cleanup.stderr.decode(errors='replace')}))
                if cleanup.returncode:
                    check = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                                           capture_output=True, timeout=10)
                    if check.returncode or 'No such container' not in cleanup.stderr.decode(errors='replace'):
                        raise ExecutionUncertain('container cleanup not confirmed')
            except (subprocess.TimeoutExpired, OSError) as exc:
                raise ExecutionUncertain('container cleanup could not be checked') from exc
    if status == 'succeeded':
        inp = json.loads((path / 'input.json').read_text())
        solution = json.loads((path / 'solution.json').read_text())
        (path / 'validation.json').write_text(json.dumps(validate(inp, solution,
            tolerance_pu=request['validation_tolerance_pu']), indent=2, allow_nan=False))
    return {'status': status, 'exit_code': exit_code, 'container_name': name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', required=True)
    parser.add_argument('--root', type=Path, default=REPO / 'data/trials')
    parser.add_argument('--max-it', type=int, default=20)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--retry', action='store_true')
    parser.add_argument('--replay-of')
    args = parser.parse_args()
    request = make_request(max_iterations=args.max_it, timeout_seconds=args.timeout)
    manifest = run_trial(args.root, args.key, request, execute_reference,
                         retry=args.retry, replay_of=args.replay_of)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest['status'] == 'succeeded' else 2


if __name__ == '__main__':
    raise SystemExit(main())
