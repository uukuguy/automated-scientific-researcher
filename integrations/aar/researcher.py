"""Actual pinned AAR AutonomousAgentLoop with the selected ASR pi runtime.

Imports real optional dependencies. This module does not emulate AAR classes or
start the legacy backend worker. The patched upstream run() is the sole outer
research-loop owner; pi owns reasoning and tool iteration within each session.
"""
import asyncio
from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time
from integrations.runtimes.session import run_session


def load_loop(checkout):
    checkout=Path(checkout).resolve()
    from .loop_patch import verify_loop_patch
    receipt=verify_loop_patch(checkout)
    from .source_integrity import verify_source_tree
    allowed={'w2s_research/research_loop/agent.py','w2s_research/research_loop/tools/findings_sync.py'}
    if (checkout/'.asr-worker-patch.json').exists():
        from .prepare_upstream import verify_worker_patch
        verify_worker_patch(checkout)
        allowed.add('w2s_research/web_ui/backend/worker.py')
    verify_source_tree(checkout,allowed_changes=allowed)
    source=checkout/'w2s_research/research_loop/agent.py'
    sys.path.insert(0,str(checkout))
    module=importlib.import_module('w2s_research.research_loop.agent')
    if Path(module.__file__).resolve()!=source:raise ValueError('upstream_module_checkout_conflict')
    return module


@dataclass
class RuntimeText:
    text: str


@dataclass
class RuntimeMessage:
    content: list


def create_researcher(checkout, *, runtime, bridge_factory, service, project, run, supervisor_token,
                      config_dir, workspace, logs_dir, prompt, limits, oauth_source=None, organization=None,event_callback=None):
    if organization is None:raise ValueError('actual_upstream_organization_required')
    upstream=load_loop(checkout)
    experiment=organization.experiment(supervisor_token,project,run)
    binding=service.get_run(supervisor_token,project,run)
    if binding['experiment_id']!='aar-experiment:'+str(experiment['id']):raise ValueError('actual_experiment_binding_required')

    class LocalSharedFindings(upstream.FindingsSync):
        def _fetch_all_findings(self):return organization.forum(supervisor_token,project)


    class PiAgent:
        async def execute(self, task):
            started=time.monotonic()
            def event(record):
                if event_callback:event_callback(record)
                if record.get('type')=='message_end':
                    message=record.get('message',{})
                    text='\n'.join(x['text'] for x in message.get('content',[]) if x.get('type')=='text')
                    if text and self.callback:self.callback(RuntimeMessage([RuntimeText(text)]))
            event.capacity_state=getattr(event_callback,'capacity_state',lambda:None)
            result=await asyncio.to_thread(run_session,runtime,bridge_factory(),config_dir=config_dir,
                native_session_id=run,prompt=task,limits=limits,oauth_source=oauth_source,on_event=event)
            self.owner.runtime_results.append(result)
            organization.sync_findings(supervisor_token,project,run)
            return upstream.AgentResult(success=result['status']=='settled',output=result,duration=time.monotonic()-started,
                iteration_count=result['tool_executions'],error=None if result['status']=='settled' else result['status'])

    class Researcher(upstream.AutonomousAgentLoop):
        def __init__(self):
            super().__init__(idea_uid=project,idea_name=project,workspace=Path(workspace),logs_dir=Path(logs_dir),
                max_runtime_seconds=limits.walltime_seconds,model=runtime.model,local_mode=True,
                max_sessions=1,max_consecutive_errors=1,
                should_continue=lambda:service.get_run(supervisor_token,project,run)['state']=='running')
            self.run_id=run
            self.runtime_results=[]
            # Remote legacy W2S MCP tools, S3 hooks and inherited research-thinking
            # calls are not in the pi workspace or curated capability pack.
            self.mcp_servers={}
            self.findings_sync=LocalSharedFindings(findings_dir=Path(workspace)/'shared_findings',poll_interval=5)

        def _get_prompt(self):
            return ('Actual AAR research owner; run '+run+'; upstream Experiment '+str(experiment['id'])+'. '
                'Shared findings are versioned local files in shared_findings/. '
                'Read the effective contract, guidance and budgets before decisions. '+prompt)

        def _create_agent(self,session_id,message_callback=None):
            agent=PiAgent();agent.owner=self;agent.callback=message_callback
            return agent

    return Researcher()


def run_research_session(runtime,bridge,*,config_dir,native_session_id,prompt,limits,oauth_source=None,on_event=None,checkout):
    """Invoke the existing AAR owner once; the upstream run() owns session flow."""
    if native_session_id!=bridge.run:raise ValueError('native_research_identity_mismatch')
    researcher=create_researcher(checkout,runtime=runtime,bridge_factory=lambda:bridge,service=bridge.service,
        project=bridge.project,run=bridge.run,supervisor_token=bridge.supervisor_token,
        config_dir=config_dir,workspace=bridge.workspace,logs_dir=Path(config_dir).parent/'aar-logs'/str(time.time_ns()),
        prompt=prompt,limits=limits,oauth_source=oauth_source,organization=bridge.organization,event_callback=on_event)
    summary=asyncio.run(researcher.run())
    if not researcher.runtime_results:raise RuntimeError('aar_no_session_dispatched:'+summary['stop_reason'])
    result=researcher.runtime_results[-1]
    receipt=json.loads((Path(checkout)/'.asr-loop-patch.json').read_text())
    result['aar_loop']=dict(owner='w2s_research.research_loop.agent.AutonomousAgentLoop.run',
        summary=summary,patch=receipt,experiment=bridge.organization.experiment(bridge.supervisor_token,bridge.project,bridge.run))
    return result
