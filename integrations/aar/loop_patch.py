"""Replay the minimal bounded-session hooks into a PRIVATE pinned AAR checkout.

The original ignored checkout is never edited. Only the existing AAR run loop
receives limits/control hooks; no additional research scheduler is introduced.
"""
import hashlib
import json
from pathlib import Path
import subprocess
from .prepare import ROOT


def expected_loop_sources(checkout):
    pin=json.loads(Path(__file__).with_name('upstream.json').read_text())
    checkout=Path(checkout).resolve()
    if checkout==(ROOT/pin['local_checkout']).resolve():raise ValueError('private_checkout_required')
    revision=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
    if revision!=pin['revision']:raise ValueError('upstream_revision_mismatch')
    relative='w2s_research/research_loop/agent.py';target=checkout/relative
    original_bytes=subprocess.check_output(['git','-C',str(checkout),'show',pin['revision']+':'+relative])
    source=original_bytes.decode()
    original=hashlib.sha256(original_bytes).hexdigest()
    if original!=pin['files'][relative]:raise ValueError('loop_source_pin_mismatch')
    changes=[
        ('    USER_INTERRUPT = "user_interrupt"', '    USER_INTERRUPT = "user_interrupt"\n    SESSION_LIMIT = "session_limit"\n    EXTERNAL_CONTROL = "external_control"\n    ERROR_LIMIT = "error_limit"'),
        ('        local_mode: bool = False,\n    ):','        local_mode: bool = False,\n        max_sessions: Optional[int] = None,\n        max_consecutive_errors: Optional[int] = None,\n        should_continue: Optional[Callable] = None,\n    ):'),
        ('        self.idea_uid = idea_uid','        for limit in (max_sessions, max_consecutive_errors):\n            if limit is not None and (type(limit) is not int or limit < 1):\n                raise ValueError("positive session limits required")\n        self.max_sessions = max_sessions\n        self.max_consecutive_errors = max_consecutive_errors\n        self.should_continue = should_continue\n        self.idea_uid = idea_uid'),
        ('        while True:\n            stop_reason = self.stop_checker.check()', '        while True:\n            if self.max_sessions is not None and self.session_count >= self.max_sessions:\n                stop_reason = StopReason.SESSION_LIMIT\n                break\n            if self.should_continue is not None and not self.should_continue():\n                stop_reason = StopReason.EXTERNAL_CONTROL\n                break\n            stop_reason = self.stop_checker.check()'),
        ('                self.stop_checker.record_error()\n                await asyncio.sleep(30)', '                self.stop_checker.record_error()\n                if self.max_consecutive_errors is not None and self.stop_checker.consecutive_errors >= self.max_consecutive_errors:\n                    stop_reason = StopReason.ERROR_LIMIT\n                    break\n                await asyncio.sleep(30)'),
    ]
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('unexpected_upstream_patch_context')
        source=source.replace(before,after,1)
    compile(source,str(target),'exec')
    sync_relative='w2s_research/research_loop/tools/findings_sync.py'
    sync_target=checkout/sync_relative
    sync_original=subprocess.check_output(['git','-C',str(checkout),'show',pin['revision']+':'+sync_relative])
    sync_source=sync_original.decode()
    old='return f"{finding_id}_{name_part}.json"'
    new='return f"{finding_id}_r{finding.get(\'asr_revision\', finding.get(\'revision\', 1))}_{name_part}.json"'
    if sync_source.count(old)!=1:raise ValueError('unexpected_findings_patch_context')
    sync_source=sync_source.replace(old,new,1)
    compile(sync_source,str(sync_target),'exec')
    receipt=dict(schema='asr-aar-loop-patch/1',upstream_revision=pin['revision'],source_sha256=original,
        patched_sha256=hashlib.sha256(source.encode()).hexdigest(),findings_sync_sha256=hashlib.sha256(sync_source.encode()).hexdigest())
    return {relative:original_bytes,sync_relative:sync_original},{relative:source.encode(),sync_relative:sync_source.encode()},receipt


def apply_loop_patch(checkout):
    checkout=Path(checkout).resolve()
    originals,patched,receipt=expected_loop_sources(checkout)
    for relative,body in originals.items():
        if (checkout/relative).read_bytes()!=body:raise ValueError('loop_source_modified')
    for relative,body in patched.items():(checkout/relative).write_bytes(body)
    (checkout/'.asr-loop-patch.json').write_text(json.dumps(receipt,indent=2))
    return receipt


def verify_loop_patch(checkout):
    checkout=Path(checkout).resolve()
    _,patched,receipt=expected_loop_sources(checkout)
    for relative,body in patched.items():
        if (checkout/relative).read_bytes()!=body:raise ValueError('patched_loop_modified')
    if json.loads((checkout/'.asr-loop-patch.json').read_text())!=receipt:raise ValueError('loop_patch_receipt_mismatch')
    return receipt

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('checkout',type=Path)
    print(json.dumps(apply_loop_patch(parser.parse_args().checkout),indent=2))
