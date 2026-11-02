"""Verify the local upstream pin before preparing a private adaptation checkout.

No upstream code is redistributed here. Missing license remains explicit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def inspect(checkout=None):
    pin=json.loads(Path(__file__).with_name('upstream.json').read_text())
    checkout=Path(checkout or ROOT/pin['local_checkout']).resolve()
    def git(*args):return subprocess.check_output(['git','-C',str(checkout),*args],text=True).strip()
    if git('rev-parse','HEAD')!=pin['revision']:raise ValueError('upstream_revision_mismatch')
    if git('status','--porcelain','--untracked-files=normal'):raise ValueError('upstream_dirty')
    for name,digest in pin['files'].items():
        if hashlib.sha256((checkout/name).read_bytes()).hexdigest()!=digest:raise ValueError('upstream_file_mismatch:'+name)
    names=git('ls-tree','-r','--name-only','HEAD').splitlines()
    licenses=[name for name in names if Path(name).name.lower().startswith(('license','copying'))]
    return dict(schema='asr-aar-preflight/1',revision=pin['revision'],files_verified=len(pin['files']),license_files=licenses,
                license_status=pin['license_status'],adaptation='ASR uses a runtime-neutral organization bridge; upstream loop/ORM not executed')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path);args=p.parse_args()
    result=inspect()
    if args.destination:
        # Refuse any existing target, including an empty directory. Never overwrite.
        if args.destination.exists():raise ValueError('destination_exists')
        pin=json.loads(Path(__file__).with_name('upstream.json').read_text())
        subprocess.run(['git','clone','--no-hardlinks','--no-checkout',str(ROOT/pin['local_checkout']),str(args.destination)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(args.destination),'checkout','--detach',pin['revision']],check=True,capture_output=True)
        result['prepared']=str(args.destination.resolve())
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
