"""Pure installation content compiler. Authority belongs to Control, not this plan."""
import hashlib
from . import _encode,material_digest
from .conversation import materials,verify
from .summary import check,_digest
from .summary_review import assess


def compile_plan(observed,request,candidate,review_request,review,*,author_session,reviewer_session,first_kept_entry_id,native_replay_ids=()):
    base=dict(schema='asr-context-installation-plan/1',installation_authorized=False)
    try:
        if observed['status']!='observed':raise ValueError('observed_conversation_required')
        if check(request,candidate)['status']!='pending_semantic_review':raise ValueError('structural_review_required')
        if _encode(review_request['payload']['original'])!=_encode(request) or _encode(review_request['payload']['candidate'])!=_encode(candidate):raise ValueError('review_content_mismatch')
        if assess(review_request,review,author_session=author_session,reviewer_session=reviewer_session)['status']!='reviewed':raise ValueError('accepted_review_required')
        snapshot=observed['conversation'];rows=snapshot['body']['messages'];source_materials=materials(snapshot)
        sources={s['id']:s['sha256'] for s in request['payload']['sources']}
        if any(sources.get(m.id)!=material_digest(m) for m in source_materials):raise ValueError('conversation_sources_missing_or_changed')
        mapping=observed['witness']['source_mapping']
        if len(mapping)!=len(rows) or [m['message_id'] for m in mapping]!=[r['id'] for r in rows]:raise ValueError('source_mapping_mismatch')
        cut=next((i for i,m in enumerate(mapping) if m['native_entry_id']==first_kept_entry_id),None)
        if cut is None or cut==0:raise ValueError('invalid_or_empty_cut')
        prefix={r['id'] for r in rows[:cut]};replay=set()
        for group in snapshot['groups']:
            if prefix.intersection(group['ids']) and set(group['ids']).intersection(snapshot['protected_ids']):replay.update(group['ids'])
        summarized=tuple(r['id'] for r in rows[:cut] if r['id'] not in replay)
        retained=tuple(r['id'] for r in rows[cut:]);replayed=tuple(r['id'] for r in rows[:cut] if r['id'] in replay)
        if not summarized:raise ValueError('no_summarized_prefix')
        replay_rows={r['id']:r for r in rows if r['id'] in replay}
        coverage=verify(snapshot,summarized_ids=summarized,retained_ids=retained,summary_source_ids=tuple(sources),replayed_ids=replayed,replay_messages=replay_rows)
        if coverage['status']!='coverage_verified':return dict(base,status=coverage['status'],reason=coverage.get('reason'),coverage=coverage)
        if type(native_replay_ids) is not tuple or len(set(native_replay_ids))!=len(native_replay_ids) or not set(native_replay_ids)<=set(replayed):raise ValueError('invalid_native_replay')
        for key in native_replay_ids:
            if replay_rows[key]['role']!='system' or not any(g['ids']==[key] for g in snapshot['groups']):raise ValueError('invalid_native_system_replay')
        native_rows=[replay_rows[key] for key in native_replay_ids]
        summary=_encode(dict(schema='asr-installed-context/1',summary=candidate['text'],
                             replayed_messages=[replay_rows[k] for k in replayed if k not in native_replay_ids],
                             native_replayed_system=[dict(source_id=r['id'],text_sha256=hashlib.sha256(r['text'].encode()).hexdigest()) for r in native_rows])).decode()
        body=dict(summary=summary,summary_sha256=hashlib.sha256(summary.encode()).hexdigest(),first_kept_entry_id=first_kept_entry_id,
                  native_replayed_messages=native_rows,source_leaf_id=observed['witness']['leaf_id'],conversation_sha256=snapshot['sha256'],candidate_sha256=_digest(candidate),coverage=coverage)
        return dict(base,status='installation_plan',**body,plan_sha256=_digest(body))
    except (ValueError,KeyError,TypeError) as error:
        return dict(base,status='rejected',reason=str(error) if isinstance(error,ValueError) else 'malformed_installation_input')
