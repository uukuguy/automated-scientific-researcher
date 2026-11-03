"""Build a minimal, hash-locked scientific worker context without repo secrets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = 'sha256:d40dc592523126c64abb42a730c4cc9652083efa5593d01e56238202200d9831'
SOURCES = (
    'research_projects/ood_augmentation/project.py',
    'research_projects/ood_augmentation/worker.py',
    'environments/scientific/calibrate.py',
    'powerflow_lab/validation.py',
    'asr_evaluation/ood_metrics.py',
    'asr_evaluation/ood_worker.py',
)


def image_id(tag):
    return subprocess.check_output(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'], text=True, timeout=20).strip()


def build(destination, proxy=None):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    if image_id('asr-matpower:8.1') != BASE:
        raise ValueError('local base image differs from pinned calibration image')
    source_hashes = {}
    for relative in SOURCES:
        body = (ROOT / relative).read_bytes()
        path = destination / 'source' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        source_hashes[relative] = hashlib.sha256(body).hexdigest()
    dockerfile = (ROOT / 'environments/scientific/Dockerfile').read_bytes()
    (destination / 'Dockerfile').write_bytes(dockerfile)
    subprocess.run(['uv', 'export', '--project', str(ROOT / 'environments/scientific'), '--locked',
                    '--no-dev', '--format', 'requirements-txt', '--no-emit-project',
                    '--output-file', str(destination / 'requirements.txt')], check=True, timeout=60, stdout=subprocess.DEVNULL)
    arguments = ['docker', 'build', '--iidfile', str(destination / 'image-id'), '-t', 'asr-scientific:ood-v1']
    if proxy:
        arguments += ['--build-arg', 'HTTP_PROXY=' + proxy, '--build-arg', 'HTTPS_PROXY=' + proxy]
    env = {k: v for k, v in os.environ.items() if not k.upper().endswith('_API_KEY')}
    with (destination / 'build.log').open('xb') as log:
        try:
            subprocess.run(arguments + [str(destination)], env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        except (subprocess.SubprocessError, OSError) as error:
            (destination / 'failure.json').write_text(json.dumps(dict(error_type=type(error).__name__,
                timeout_seconds=600, recovery='Retain this context/log. Reconcile any build before a new explicit invocation.')))
            raise
    if image_id('asr-matpower:8.1') != BASE:
        raise ValueError('base tag changed during build')
    record = dict(schema='asr-scientific-image/1', image_id=(destination / 'image-id').read_text().strip(),
                  base_image_id=BASE, sources=source_hashes,
                  uv_lock_sha256=hashlib.sha256((ROOT / 'environments/scientific/uv.lock').read_bytes()).hexdigest(),
                  requirements_sha256=hashlib.sha256((destination / 'requirements.txt').read_bytes()).hexdigest(),
                  dockerfile_sha256=hashlib.sha256(dockerfile).hexdigest())
    (destination / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--proxy')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.proxy), indent=2))
