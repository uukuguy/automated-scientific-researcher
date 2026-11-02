"""Finite curated skill loading and exact read exceptions; no model calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from integrations.runtimes.pi import Limits,PiRuntime,RuntimeFailure
import test_runtimes as runtime_fixtures


class SkillPackTests(unittest.TestCase):
    def fixture(self,root):
        pack=json.loads(Path('integrations/runtimes/capabilities.json').read_text())
        pack['skills']=[]
        for name in ('scientific-reasoning','critical-appraisal'):
            relative='skills/'+name+'/SKILL.md'
            path=root/relative;path.parent.mkdir(parents=True)
            path.write_text('---\nname: '+name+'\ndescription: Test curated methodology only\n---\n\nCheck claims against evidence.\n')
            pack['skills'].append(dict(id=name+'/1',name=name,path=relative,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        manifest=root/'capabilities.json';manifest.write_text(json.dumps(pack))
        return manifest,pack

    def test_multiple_skills_frozen_readonly_and_passed_explicitly_with_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest,pack=self.fixture(root)
            executable=runtime_fixtures.RuntimeTests().fake(d,[{'type':'agent_settled'}])
            popen=subprocess.Popen
            with patch('integrations.runtimes.pi.subprocess.Popen',wraps=popen) as spawn:
                result=PiRuntime(executable=executable,model='test',capabilities_path=manifest).run(workspace=root,config_dir=root,session_id='skills',prompt='test',limits=Limits(2,2,2),bridge_url='http://localhost:1',bridge_token='test')
            argv=spawn.call_args.args[0];env=spawn.call_args.kwargs['env']
            skills=[argv[index+1] for index,value in enumerate(argv) if value=='--skill']
            self.assertEqual(len(skills),2)
            self.assertIn('--no-skills',argv)
            self.assertEqual(json.loads(env['ASR_SKILL_PATHS']),skills)
            self.assertEqual(env['ASR_SKILL_PATH'],skills[0])
            self.assertEqual(result['capability_pack_sha256'],hashlib.sha256(manifest.read_bytes()).hexdigest())
            self.assertEqual([item['id'] for item in result['capability_skills']],[item['id'] for item in pack['skills']])
            for source,frozen,provenance in zip(pack['skills'],skills,result['capability_skills']):
                self.assertEqual((root/source['path']).read_bytes(),Path(frozen).read_bytes())
                self.assertEqual(Path(frozen).stat().st_mode&0o777,0o400)
                self.assertEqual(provenance['sha256'],source['sha256'])
                self.assertEqual(provenance['frozen_path'],frozen)

    def test_second_skill_tamper_rejects_before_version_probe_or_spawn(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest,pack=self.fixture(root)
            (root/pack['skills'][1]['path']).write_text('changed')
            with patch('integrations.runtimes.pi.subprocess.check_output') as version,patch('integrations.runtimes.pi.subprocess.Popen') as spawn:
                with self.assertRaisesRegex(RuntimeFailure,'skill_hash_mismatch'):
                    PiRuntime(model='test',capabilities_path=manifest).run(workspace=root,config_dir=root,session_id='skills',prompt='test',limits=Limits(1,1,1),bridge_url='http://localhost:1',bridge_token='test')
                version.assert_not_called();spawn.assert_not_called()

    def test_duplicate_traversal_absolute_name_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest,original=self.fixture(root)
            PiRuntime(model='test',capabilities_path=manifest).preflight_capabilities()
            for kind in ('duplicate','traversal','absolute','name','header','symlink'):
                pack=json.loads(json.dumps(original));path=root/pack['skills'][1]['path'];body=path.read_bytes()
                if kind=='duplicate':pack['skills'].append(dict(pack['skills'][0]))
                elif kind=='traversal':pack['skills'][1]['path']='skills/../critical-appraisal/SKILL.md'
                elif kind=='absolute':pack['skills'][1]['path']=str(path)
                elif kind=='name':pack['skills'][1]['name']='other-name'
                elif kind=='header':
                    path.write_text('---\nname: other-name\n---\nWrong skill identity\n')
                    pack['skills'][1]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
                elif kind=='symlink':path.unlink();path.symlink_to(root/pack['skills'][0]['path'])
                manifest.write_text(json.dumps(pack))
                try:
                    with self.assertRaises(RuntimeFailure,msg=kind):PiRuntime(model='test',capabilities_path=manifest).preflight_capabilities()
                finally:
                    if path.is_symlink():path.unlink()
                    path.write_bytes(body)

    def test_old_profile_requires_its_pinned_adapter_before_any_launch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest,pack=self.fixture(root)
            pack['id']='powerflow-calibration-smoke/2'
            pack['tools']=[tool for tool in pack['tools'] if tool not in ('asr.resolve_library','asr.query_docs','asr.search_literature')]
            manifest.write_text(json.dumps(pack))
            with patch('integrations.runtimes.pi.subprocess.check_output') as version,patch('integrations.runtimes.pi.subprocess.Popen') as spawn:
                with self.assertRaisesRegex(RuntimeFailure,'capability_pack_version_mismatch'):
                    PiRuntime(model='test',capabilities_path=manifest).run(workspace=root,config_dir=root,session_id='skills',prompt='test',limits=Limits(1,1,1),bridge_url='http://localhost:1',bridge_token='test')
                version.assert_not_called();spawn.assert_not_called()

    def test_manifest_symlink_is_not_a_registry_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest,_=self.fixture(root)
            alias=root/'alias.json';alias.symlink_to(manifest)
            with self.assertRaisesRegex(RuntimeFailure,'manifest_symlink_forbidden'):
                PiRuntime(model='test',capabilities_path=alias).preflight_capabilities()

    def test_frozen_skill_inside_workspace_is_still_readonly(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);skill=root/'frozen'/'SKILL.md';skill.parent.mkdir();skill.write_text('curated')
            module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
            code=f'''import extension from {json.dumps(module)};
const handlers={{}};globalThis.fetch=async()=>({{ok:true,json:async()=>({{}})}});
extension({{on:(name,handler)=>handlers[name]=handler,registerTool:()=>{{}}}});
for(const toolName of ['write','edit']) {{
 const decision=await handlers.tool_call({{toolName,toolCallId:toolName,input:{{path:'frozen/SKILL.md'}}}});
 if(!decision?.block)throw new Error('frozen skill modification allowed');
}}'''
            env=dict(os.environ,ASR_WORKSPACE=str(root),ASR_SKILL_PATHS=json.dumps([str(skill.resolve())]),ASR_MAX_TURNS='1',ASR_MAX_TOOLS='3',ASR_DEADLINE_MS=str(int((time.time()+10)*1000)))
            result=subprocess.run(['node','--input-type=module','-e',code],env=env,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr.decode())

    def test_exact_multiple_skill_read_exceptions_block_siblings_undeclared_and_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);work=root/'work';work.mkdir();outside=root/'frozen';outside.mkdir()
            first=outside/'first.md';second=outside/'second.md'
            first.write_text('one');second.write_text('two')
            module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
            code=f'''import extension from {json.dumps(module)};
const handlers={{}};
globalThis.fetch=async()=>({{ok:true,json:async()=>({{activity_id:'permit'}})}});
extension({{on:(name,handler)=>handlers[name]=handler,registerTool:()=>{{}}}});
for(const path of {json.dumps([str(first),str(second)])}) {{
 const event={{toolName:'read',toolCallId:path,input:{{path}}}};
 const decision=await handlers.tool_call(event);
 if(decision?.block||event.input.path!==path)throw new Error('declared read denied '+path);
}}
for(const [toolName,path] of {json.dumps([['read',str(outside/'sibling.md')],['read',str(root/'undeclared.md')],['write',str(second)],['read',str(second)+'/../sibling.md']])}) {{
 const decision=await handlers.tool_call({{toolName,toolCallId:path,input:{{path}}}});
 if(!decision?.block)throw new Error('undeclared access allowed '+path);
}}'''
            env=dict(os.environ,ASR_WORKSPACE=str(work),ASR_SKILL_PATH=str(first),ASR_SKILL_PATHS=json.dumps([str(first),str(second)]),ASR_MAX_TURNS='1',ASR_MAX_TOOLS='20',ASR_DEADLINE_MS=str(int((time.time()+10)*1000)))
            result=subprocess.run(['node','--input-type=module','-e',code],env=env,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr.decode())

if __name__=='__main__':unittest.main()
