"""Generate a private source checkout and apply only tracked ASR patches.

No upstream files are vendored. Licensing remains explicitly unresolved in the
pin. Source inspection/patching here authorizes no model or legacy worker run.
"""
import argparse
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
from .prepare import ROOT, inspect


def prepare_checkout(destination):
    pin=json.loads(Path(__file__).with_name('upstream.json').read_text())
    inspect()
    destination=Path(destination).resolve()
    if destination.exists(): raise ValueError('destination_exists')
    subprocess.run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(ROOT/pin['local_checkout']),str(destination)],check=True)
    subprocess.run(['git','-C',str(destination),'checkout','--quiet','--detach',pin['revision']],check=True)
    patch=Path(__file__).with_name('upstream_worker.patch').resolve()
    subprocess.run(['git','-C',str(destination),'apply','--check',str(patch)],check=True)
    subprocess.run(['git','-C',str(destination),'apply',str(patch)],check=True)
    source=destination/'w2s_research/web_ui/backend/worker.py'
    receipt=dict(schema='asr-aar-worker-patch/1',upstream_revision=pin['revision'],patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),patched_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (destination/'.asr-worker-patch.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return destination


def verify_worker_patch(checkout):
    """Derive trusted bytes from the pinned blob and tracked patch, not receipt."""
    checkout=Path(checkout).resolve()
    pin=json.loads(Path(__file__).with_name('upstream.json').read_text())
    revision=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
    if revision!=pin['revision']: raise ValueError('upstream_revision_mismatch')
    relative='w2s_research/web_ui/backend/worker.py'
    original=subprocess.check_output(['git','-C',str(checkout),'show',pin['revision']+':'+relative])
    patch=Path(__file__).with_name('upstream_worker.patch').resolve()
    # git apply operates only on this newly-created isolated original, so mutable
    # checkout/index flags and a forged receipt cannot redefine expected bytes.
    with tempfile.TemporaryDirectory(prefix='asr-worker-verify-') as temporary:
        target=Path(temporary)/relative;target.parent.mkdir(parents=True)
        target.write_bytes(original)
        subprocess.run(['git','-C',temporary,'apply',str(patch)],check=True,capture_output=True)
        expected=target.read_bytes()
    target=checkout/relative
    expected_receipt=dict(schema='asr-aar-worker-patch/1',upstream_revision=pin['revision'],patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),patched_sha256=hashlib.sha256(expected).hexdigest())
    if target.is_symlink() or target.read_bytes()!=expected: raise ValueError('worker_guard_patch_modified')
    if json.loads((checkout/'.asr-worker-patch.json').read_text())!=expected_receipt: raise ValueError('worker_guard_receipt_modified')
    return expected_receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',required=True,type=Path)
    args=parser.parse_args()
    print(prepare_checkout(args.destination))

if __name__=='__main__': main()
