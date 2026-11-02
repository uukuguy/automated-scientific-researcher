"""Verify physical upstream dependency bytes against the pinned Git tree.

Index flags and mutable receipts are not authority. The caller must independently
verify every explicitly allowed transformation against its tracked patch logic.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil


def verify_source_tree(checkout, *, allowed_changes):
    checkout=Path(checkout).resolve()
    pin=json.loads(Path(__file__).with_name('upstream.json').read_text())
    def git(*args):return subprocess.check_output(['git','-C',str(checkout),*args])
    if git('rev-parse','HEAD').decode().strip()!=pin['revision']:raise ValueError('upstream_revision_mismatch')
    records=git('ls-tree','-r','-z',pin['revision'],'--','w2s_research').split(b'\0')
    tracked=set()
    for record in records:
        if not record:continue
        metadata,rawname=record.split(b'\t',1);mode,kind,blob=metadata.split()
        name=rawname.decode();tracked.add(name);path=checkout/name
        if kind!=b'blob' or mode not in (b'100644',b'100755') or path.is_symlink() or not path.is_file():
            raise ValueError('unexpected_upstream_source_modified')
        if name in allowed_changes:continue
        body=path.read_bytes()
        actual=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest().encode()
        if actual!=blob:raise ValueError('unexpected_upstream_source_modified')
    # Files staged under nonstandard index flags are still visible in the actual
    # filesystem inventory and cannot introduce a new importable source module.
    for path in (checkout/'w2s_research').rglob('*'):
        if path.is_file() and path.suffix in ('.py','.so','.pth') and path.relative_to(checkout).as_posix() not in tracked:
            raise ValueError('unexpected_upstream_source_added')
    # Prepared-checkout bytecode is disposable and is not source authority.
    # Purge it before imports so timestamp-valid injected caches cannot bypass
    # the physical .py verification. Never follow a cache symlink.
    for cache in list((checkout/'w2s_research').rglob('__pycache__')):
        if cache.is_symlink():raise ValueError('unexpected_upstream_bytecode_symlink')
        if cache.exists():shutil.rmtree(cache)
    for bytecode in (checkout/'w2s_research').rglob('*.pyc'):
        if bytecode.is_symlink() or bytecode.relative_to(checkout).as_posix() in tracked:raise ValueError('unexpected_upstream_bytecode')
        bytecode.unlink()
    return tracked
