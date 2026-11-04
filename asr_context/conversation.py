"""Runtime-neutral visible interaction grouping and structural coverage proofs."""
from dataclasses import dataclass,asdict
import json
from . import Material,_encode
from .summary import _digest


@dataclass(frozen=True)
class Message:
    id: str
    role: str
    text: str
    calls: tuple[tuple[str,str],...] = ()
    result_for: str | None = None
    tool_name: str | None = None
    negative: bool = False
    protected: bool = False

    def __post_init__(self):
        if type(self.id) is not str or not self.id or self.role not in ('system','user','assistant','tool','memory') or type(self.text) is not str:raise ValueError('invalid_conversation_message')
        if type(self.calls) is not tuple or any(type(c) is not tuple or len(c)!=2 or any(type(s) is not str or not s for s in c) for c in self.calls):raise ValueError('invalid_conversation_calls')
        if self.calls and self.role!='assistant':raise ValueError('invalid_call_role')
        if self.role=='tool':
            if any(type(v) is not str or not v for v in (self.result_for,self.tool_name)):raise ValueError('invalid_tool_result')
        elif self.result_for is not None or self.tool_name is not None:raise ValueError('invalid_result_role')
        if type(self.negative) is not bool or type(self.protected) is not bool:raise ValueError('invalid_conversation_flags')


def capture(scope,messages,*,source_revision,keep_recent_groups):
    if any(type(v) is not str or not v for v in (scope,source_revision)) or type(keep_recent_groups) is not int or keep_recent_groups<1:raise ValueError('invalid_conversation_scope_or_policy')
    rows=list(messages)
    if any(type(r) is not Message for r in rows) or len({r.id for r in rows})!=len(rows):raise ValueError('duplicate_or_invalid_message')
    groups=[];seen_calls=set();index=0;open_calls=[]
    while index<len(rows):
        row=rows[index]
        if row.role=='tool':raise ValueError('orphan_tool_result')
        entries=[row];index+=1;pending={}
        for call,name in row.calls:
            if call in seen_calls:raise ValueError('duplicate_tool_call')
            seen_calls.add(call);pending[call]=name
        while pending and index<len(rows):
            result=rows[index]
            if result.role=='system':entries.append(result);index+=1;continue
            if result.role!='tool':break
            if pending.get(result.result_for)!=result.tool_name:raise ValueError('tool_result_mismatch')
            del pending[result.result_for];entries.append(result);index+=1
        open_calls.extend(pending)
        groups.append(dict(id='interaction:'+row.id,ids=[r.id for r in entries],complete=not pending,
                           negative=any(r.negative for r in entries),protected=any(r.protected or r.role=='system' for r in entries)))
    protected={r.id for r in rows if r.protected or r.role=='system'}
    users=[r.id for r in rows if r.role=='user']
    if users:protected.add(users[-1])
    roles={r.id:r.role for r in rows}
    recent=[g for g in groups if not all(roles[i]=='system' for i in g['ids'])][-keep_recent_groups:]
    negatives=[g for g in groups if g['negative']]
    for group in [*recent,*(negatives[-1:]),*(g for g in groups if not g['complete'] or g['protected'])]:protected.update(group['ids'])
    # Explicit protection of any member protects the entire interaction.
    for group in groups:
        if protected.intersection(group['ids']):protected.update(group['ids'])
    body=json.loads(_encode(dict(scope=scope,source_revision=source_revision,keep_recent_groups=keep_recent_groups,messages=[asdict(r) for r in rows])))
    return dict(schema='asr-conversation-snapshot/1',body=body,sha256=_digest(body),groups=groups,protected_ids=[r.id for r in rows if r.id in protected],open_calls=open_calls)


def _rebuild(snapshot):
    body=snapshot['body']
    if snapshot['schema']!='asr-conversation-snapshot/1' or _digest(body)!=snapshot['sha256']:raise ValueError('conversation_snapshot_changed')
    rows=[Message(**dict(r,calls=tuple(tuple(c) for c in r['calls']))) for r in body['messages']]
    rebuilt=capture(body['scope'],rows,source_revision=body['source_revision'],keep_recent_groups=body['keep_recent_groups'])
    if rebuilt!=snapshot:raise ValueError('conversation_metadata_changed')
    return rebuilt,rows


def materials(snapshot):
    rebuilt,rows=_rebuild(snapshot);membership={i:g for g in rebuilt['groups'] for i in g['ids']}
    return [Material(r.id,_digest(asdict(r)),r.text,protected=r.id in rebuilt['protected_ids'],group=membership[r.id]['id'],complete=membership[r.id]['complete']) for r in rows]


def verify(snapshot,*,summarized_ids,retained_ids,summary_source_ids,replayed_ids=(),replay_messages=None):
    base=dict(schema='asr-conversation-coverage/1',installation_authorized=False)
    try:
        rebuilt,rows=_rebuild(snapshot)
        for values in (summarized_ids,retained_ids,summary_source_ids,replayed_ids):
            if type(values) is not tuple or any(type(v) is not str for v in values) or len(set(values))!=len(values):raise ValueError('invalid_coverage_ids')
        summary=set(summarized_ids);retained=set(retained_ids);replayed=set(replayed_ids);all_ids={r.id for r in rows}
        if summary&retained or summary&replayed or retained&replayed or summary|retained|replayed!=all_ids:raise ValueError('coverage_gap_or_overlap')
        if not summary<=set(summary_source_ids):raise ValueError('summary_source_coverage_missing')
        if summary.intersection(rebuilt['protected_ids']):raise ValueError('protected_interaction_removed')
        if replay_messages is None:
            if any(r.id in replayed and r.role!='system' for r in rows):raise ValueError('only_system_context_can_be_replayed')
        elif type(replay_messages) is not dict or set(replay_messages)!=replayed or any(_encode(replay_messages[r.id])!=_encode(asdict(r)) for r in rows if r.id in replayed):
            raise ValueError('exact_replay_required')
        for group in rebuilt['groups']:
            if sum(bool(set(group['ids'])&bucket) for bucket in (summary,retained,replayed))!=1:raise ValueError('interaction_split')
        if rebuilt['open_calls']:return dict(base,status='deferred',reason='open_tool_calls',open_calls=rebuilt['open_calls'])
        return dict(base,status='coverage_verified',changed=bool(summary),conversation_sha256=snapshot['sha256'],source_revision=snapshot['body']['source_revision'],
                    summarized_ids=list(summarized_ids),retained_ids=list(retained_ids),replayed_ids=list(replayed_ids),summary_source_ids=list(summary_source_ids))
    except (ValueError,KeyError,TypeError) as error:
        return dict(base,status='rejected',reason=str(error) if isinstance(error,ValueError) else 'malformed_conversation_coverage')
