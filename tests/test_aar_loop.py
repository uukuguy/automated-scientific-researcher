"""Pinned real upstream-loop tests; optional CPU dependencies, no model calls."""
import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from integrations.aar.loop_patch import apply_loop_patch,verify_loop_patch
from integrations.aar.prepare import ROOT

class PatchTests(unittest.TestCase):
    def test_patch_refuses_original_and_dirty_source(self):
        pin=json.loads(Path('integrations/aar/upstream.json').read_text())
        source=ROOT/pin['local_checkout']
        with self.assertRaisesRegex(ValueError,'private_checkout_required'):apply_loop_patch(source)
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'aar'
            subprocess.run(['git','clone','--quiet','--no-hardlinks',str(source),str(target)],check=True)
            receipt=apply_loop_patch(target)
            self.assertNotEqual(receipt['source_sha256'],receipt['patched_sha256'])
            from integrations.aar.source_integrity import verify_source_tree
            cache=target/'w2s_research/__pycache__';cache.mkdir();(cache/'config.forged.pyc').write_bytes(b'forged-bytecode')
            verify_source_tree(target,allowed_changes={'w2s_research/research_loop/agent.py','w2s_research/research_loop/tools/findings_sync.py'})
            self.assertFalse(cache.exists())
            with self.assertRaisesRegex(ValueError,'loop_source_modified'):apply_loop_patch(target)
            source=target/'w2s_research/research_loop/agent.py'
            source.write_text(source.read_text()+'\n# forged checkout edit\n')
            import hashlib
            receipt['patched_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
            (target/'.asr-loop-patch.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'patched_loop_modified'):verify_loop_patch(target)
            from integrations.aar.source_integrity import verify_source_tree
            subprocess.run(['git','-C',str(target),'update-index','--assume-unchanged','w2s_research/config.py'],check=True)
            config=target/'w2s_research/config.py';config.write_text(config.read_text()+'\n# tamper imported dependency\n')
            with self.assertRaisesRegex(ValueError,'unexpected_upstream_source_modified'):
                verify_source_tree(target,allowed_changes={'w2s_research/research_loop/agent.py','w2s_research/research_loop/tools/findings_sync.py'})

    @unittest.skipUnless(importlib.util.find_spec('claude_agent_sdk'),'optional aar dependencies unavailable')
    def test_actual_upstream_run_respects_session_and_external_limits(self):
        from integrations.aar.researcher import load_loop
        pin=json.loads(Path('integrations/aar/upstream.json').read_text())
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'aar'
            subprocess.run(['git','clone','--quiet','--no-hardlinks',str(ROOT/pin['local_checkout']),str(target)],check=True)
            apply_loop_patch(target);upstream=load_loop(target)
            class Probe(upstream.AutonomousAgentLoop):
                async def _run_session(self): self.invocations+=1
            instance=Probe(idea_uid='test',idea_name='test',local_mode=True,logs_dir=Path(d)/'logs',max_runtime_seconds=1,max_sessions=1,max_consecutive_errors=1)
            instance.invocations=0
            result=asyncio.run(instance.run())
            self.assertEqual(instance.invocations,1);self.assertEqual(result['stop_reason'],'session_limit')
            instance.should_continue=lambda:False
            instance.session_count=0
            result=asyncio.run(instance.run())
            self.assertEqual(instance.invocations,1);self.assertEqual(result['stop_reason'],'external_control')
            sync=__import__('w2s_research.research_loop.tools.findings_sync',fromlist=['save_finding_to_dir'])
            one=sync.save_finding_to_dir({'id':1,'idea_name':'same','asr_revision':1},Path(d)/'shared')
            two=sync.save_finding_to_dir({'id':1,'idea_name':'same','asr_revision':2},Path(d)/'shared')
            self.assertNotEqual(one,two);self.assertTrue(one.exists());self.assertTrue(two.exists())
            instance.should_continue=lambda:True
            async def failure():
                instance.invocations+=1
                raise RuntimeError('deliberate interface failure; no provider call')
            instance._run_session=failure
            import contextlib,io
            with contextlib.redirect_stderr(io.StringIO()):result=asyncio.run(instance.run())
            self.assertEqual(result['stop_reason'],'error_limit');self.assertEqual(instance.invocations,2)


