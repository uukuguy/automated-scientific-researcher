"""Generate a private source checkout and apply only tracked ASR patches.

No upstream files are vendored. Licensing remains explicitly unresolved in the
pin. Source inspection/patching here authorizes no model or legacy worker run.
"""
import argparse
import json
import hashlib
from pathlib import Path
import subprocess
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',required=True,type=Path)
    args=parser.parse_args()
    print(prepare_checkout(args.destination))

if __name__=='__main__': main()
