"""Trusted container entrypoint. Never imports or executes candidate material."""
import importlib.util
import json
import os
from pathlib import Path
import socket


def probe():
    checks = {}
    for name, path in [('input_readonly', '/inputs/write-probe'),
                       ('evaluator_readonly', '/evaluator/write-probe'),
                       ('rootfs_readonly', '/write-probe')]:
        try:
            Path(path).write_text('probe')
            checks[name] = False
        except OSError:
            checks[name] = True
    checks['nonroot'] = os.getuid() != 0
    checks['no_docker_socket'] = not Path('/var/run/docker.sock').exists()
    checks['no_candidate_workspace'] = not Path('/workspace').exists()
    checks['no_auth_environment'] = not any(name in os.environ for name in (
        'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'AWS_ACCESS_KEY_ID',
        'CODEX_HOME', 'SSH_AUTH_SOCK'))
    readable_auth = False
    for path in ('/tmp/.codex/auth.json', '/root/.codex/auth.json', '/tmp/.pi/agent/auth.json'):
        try:
            with Path(path).open('rb'):
                readable_auth = True
        except OSError:
            pass
    checks['no_readable_native_auth_files'] = not readable_auth
    checks['only_loopback_interface'] = {p.name for p in Path('/sys/class/net').iterdir()} == {'lo'}
    with socket.socket() as connection:
        connection.settimeout(.5)
        try:
            connection.connect(('198.51.100.1', 443))
            checks['external_network_blocked'] = False
        except OSError:
            checks['external_network_blocked'] = True
    return dict(kind='isolation_probe', checks=checks,
                limit='Probes cover this container configuration, not host processes or arbitrary candidate execution.')


def main():
    request = json.loads(Path('/inputs/evaluation-request.json').read_text())
    if request['mode'] == 'probe':
        result = probe()
    else:
        spec = importlib.util.spec_from_file_location('trusted_validation', '/evaluator/validation.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = json.loads(Path('/inputs/input.json').read_text())
        solution = json.loads(Path('/inputs/solution.json').read_text())
        result = module.validate(original, solution, tolerance_pu=request['tolerance_pu'])
    Path('/output/result.json').write_text(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
