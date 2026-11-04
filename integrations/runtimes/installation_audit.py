"""Read-only audit of actual installation evidence; never reruns a model."""
import hashlib,json,sqlite3
from pathlib import Path
from .pi_context import observe
from .summary_acceptance import parse_reply
from .process import verify_process_exit
from asr_service.context_sources import _observe


def audit(root):
    root=Path(root).resolve();identity=json.loads((root/'identity.json').read_text());project=identity['project_id'];run=identity['research_run_id']
    with sqlite3.connect((root/'control.db').as_uri()+'?mode=ro',uri=True) as db:
        requests={(scope,key):json.loads(record) for scope,key,record in db.execute('SELECT scope,request_key,record FROM asr_requests WHERE project=?',(project,))}
        sessions=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_runtime_sessions WHERE project=? AND run=?',(project,run))]
        state=json.loads(db.execute('SELECT record FROM asr_runs WHERE project=? AND run=?',(project,run)).fetchone()[0])
        trials=db.execute('SELECT COUNT(*) FROM asr_dispatch WHERE project=? AND run=?',(project,run)).fetchone()[0]
        limits={dimension:amount for dimension,amount in db.execute('SELECT dimension,amount FROM asr_budget_limits WHERE project=?',(project,))}
    results=[]
    expected={v['id']:v['value'] for v in json.loads(Path('tests/fixtures/research_context/summary-fidelity.json').read_text())['obligations']}
    for work in sorted(root.glob('installation-*')):
        if not (work/'success.json').is_file():continue
        stage=json.loads((work/'installation-plan.json').read_text());stage_id=stage['stage_id']
        ticket=next(value['ticket'] for value in requests.values() if value.get('ticket',{}).get('stage_id')==stage_id)
        raw=Path(ticket['reader']['path']).read_bytes();records=[json.loads(line) for line in raw.splitlines() if line.strip()]
        entry=next(r for r in records if r.get('type')=='compaction' and r.get('details',{}).get('asr_installation_ticket')==ticket['ticket_id'])
        scope=json.dumps([project,run,'generator'],ensure_ascii=False,separators=(',',':'))
        observed=observe(ticket['reader']['path'],expected_session_id=ticket['native_session_id'],leaf_id=entry['id'],scope=scope,keep_recent_groups=ticket['reader']['keep_recent_groups'],max_journal_bytes=ticket['reader']['max_journal_bytes'])
        if observed['status']!='observed':raise ValueError('audit_projection_deferred')
        owner_scope=json.dumps([run,'generator'],ensure_ascii=False,separators=(',',':'))
        source=requests[('context-source:'+owner_scope,stage['preparation']['source_registration'])]['observation']
        source_registration=requests[('context-source:'+owner_scope,stage['preparation']['source_registration'])]
        redecoded=_observe(source_registration['reader'])
        source_rows={r['id']:r for r in source['conversation']['body']['messages']}
        projected={r['id'] for r in observed['conversation']['body']['messages']}
        envelope=json.loads(entry['summary']);coverage=ticket['plan']['coverage']
        native_replay=ticket['plan'].get('native_replayed_messages',[])
        native_ids={r['id'] for r in native_replay}
        native=json.loads((work/'05-installed-continuation'/'runtime-result.json').read_text());reply=parse_reply(native)
        reviewer_result=json.loads((work/'04-review'/'runtime-result.json').read_text());review=parse_reply(reviewer_result)
        summary_result=json.loads((work/'03-summary'/'runtime-result.json').read_text());candidate=parse_reply(summary_result)
        checks=dict(source_snapshot_redecoded_equal=redecoded.get('status')=='observed' and redecoded['conversation']['body']['messages']==source['conversation']['body']['messages'],original_prefix_preserved=hashlib.sha256(raw[:ticket['before_journal_bytes']]).hexdigest()==ticket['before_journal_sha256'],
                    native_from_hook=entry.get('fromHook') is True,parent_matches=entry['parentId']==ticket['source_cursor']['leaf_id'],
                    native_content_matches=all(entry.get(k)==v for k,v in ticket['compaction'].items()),
                    summary_hash_matches=hashlib.sha256(entry['summary'].encode()).hexdigest()==ticket['summary_sha256'],
                    protected_replay_exact=envelope['replayed_messages']==[source_rows[key] for key in coverage['replayed_ids'] if key not in native_ids],
                    native_system_replay_exact=all(any(r['role']=='system' and r['text']==original['text'] for r in observed['conversation']['body']['messages']) for original in native_replay),
                    summarized_ids_absent=not set(coverage['summarized_ids'])&projected,
                    retained_ids_present=set(coverage['retained_ids'])<=projected,
                    candidate_prose_unchanged=envelope['summary']==candidate['text'],
                    separate_review_sessions=summary_result['runtime_claim']['session_id']!=reviewer_result['runtime_claim']['session_id'],
                    review_accepted=review['verdict']=='accept' and not review['issues'],
                    continued_with_subscription=native['status']=='settled' and native['provider']=='openai-codex',
                    recalled_facts=all(reply.get(k)==v for k,v in expected.items()))
        # The second cycle must receive the trusted receipt before prompting.
        events=[json.loads(line).get('event',{}) for line in (work/'05-installed-continuation'/'events.jsonl').read_text().splitlines()]
        verified=[i for i,e in enumerate(events) if e.get('type')=='asr_context_installation' and e.get('status')=='verified']
        compact=[i for i,e in enumerate(events) if e.get('type')=='response' and e.get('id')=='context-install']
        prompt=[i for i,e in enumerate(events) if e.get('type')=='response' and e.get('id')=='prompt']
        guard_observed=bool(verified and compact and prompt and verified[-1]<compact[0]<prompt[0])
        if work.name!='installation-001':checks['verified_before_next_prompt']=guard_observed
        if not all(checks.values()):raise ValueError('installation_audit_failed:'+work.name+':'+','.join(k for k,v in checks.items() if not v))
        before=source['conversation']['body']['messages'];after=observed['conversation']['body']['messages']
        results.append(dict(cycle=work.name,ticket_id=ticket['ticket_id'],entry_id=entry['id'],checks=checks,guard_observed=guard_observed,
                            source_messages=len(before),projected_messages=len(after),summarized_messages=len(coverage['summarized_ids']),replayed_messages=len(coverage['replayed_ids']),retained_messages=len(coverage['retained_ids']),
                            before_visible_bytes=sum(len(r['text'].encode()) for r in before),after_visible_bytes=sum(len(r['text'].encode()) for r in after),
                            before_journal_bytes=ticket['before_journal_bytes'],before_journal_sha256=ticket['before_journal_sha256'],summary_sha256=ticket['summary_sha256'],projection_sha256=observed['witness']['projection_sha256'],fact_checks={k:reply.get(k)==v for k,v in expected.items()}))
    for session in sessions:
        if session['state']!='exited' or session.get('execution_exited') is not True:raise ValueError('runtime_not_drained')
        verify_process_exit(session['process_identity'],terminate=False)
    return dict(schema='asr-context-installation-audit/1',status='passed',cycles=results,model=identity['model'],total_model_sessions=len(sessions),all_processes_exited=True,new_scientific_trials=trials,
                budget_limits=limits,total_model_walltime_ms=sum(s['actual_walltime_ms'] for s in sessions),provider_payload_verified=False,
                boundary='实际订阅、固定pi SDK写入/投影与后续事实任务；同模型分开复核，不是科学验证或任意长期自动恢复。')
