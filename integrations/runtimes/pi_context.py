"""Read-only adapter from pinned pi journals to runtime-neutral visible records.

The leaf must be explicitly supplied. An offline selection is not proof of an
active Runtime's cursor. Logical SDK projection is not the provider wire payload.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from asr_context import _encode
from asr_context.conversation import Message,capture
from .environment import COMMON_ENVIRONMENT,build_environment


def _digest(value):return hashlib.sha256(_encode(value)).hexdigest()


def sdk_projection(entries,leaf,*,capacity_policy_path=None):
    from .capacity_policy import load_policy
    policy=load_policy(capacity_policy_path)
    binary=shutil.which('pi')
    if not binary:raise ValueError('pi_not_installed')
    index=Path(binary).resolve().parents[1]/'index.js'
    package=json.loads((index.parent.parent/'package.json').read_text())
    if package['name']!='@earendil-works/pi-coding-agent' or package['version']!='1.5.0':raise ValueError('pi_sdk_version_mismatch')
    result=subprocess.run(['node',str(Path(__file__).with_name('pi_context_projection.mjs')),str(index)],
        input=_encode(dict(entries=entries,leafId=leaf)),capture_output=True,timeout=policy['limits']['projection_seconds']['value'],
        env=build_environment(COMMON_ENVIRONMENT,runtime='pi',provider='openai-codex'))
    if result.returncode:raise ValueError('pi_projection_failed')
    projection=json.loads(result.stdout)
    projection['capacity_policy_sha256']=policy['sha256']
    projection['projection_timeout_seconds']=policy['limits']['projection_seconds']['value']
    projection['projection_helper_sha256']=hashlib.sha256(Path(__file__).with_name('pi_context_projection.mjs').read_bytes()).hexdigest()
    projection['sdk_index_sha256']=hashlib.sha256(index.read_bytes()).hexdigest()
    return projection


def observe(path,*,expected_session_id,leaf_id,scope,keep_recent_groups,max_journal_bytes,projector=sdk_projection):
    if type(max_journal_bytes) is not int or max_journal_bytes<1:raise ValueError('invalid_journal_capacity')
    redactions=0;call_mapping={}
    def clean(value):
        nonlocal redactions
        if isinstance(value,dict):
            result={}
            for key,item in value.items():
                normalized=key.lower().replace('_','').replace('-','')
                if normalized in {'accesstoken','refreshtoken','apikey','authorization','cookie','password','thinkingsignature','thoughtsignature','encryptedcontent'}:
                    result[key]='[REDACTED]';redactions+=1
                else:result[key]=clean(item)
            return result
        if isinstance(value,list):return [clean(v) for v in value]
        if isinstance(value,str):
            text=re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+','Bearer [REDACTED]',value)
            text=re.sub(r'(?i)([?&](?:access_token|refresh_token|api_key)=)[^&\s]+',r'\1[REDACTED]',text)
            redactions+=text!=value;return text
        return value
    def content(value):
        nonlocal redactions
        if isinstance(value,str):return clean(value)
        if type(value) is not list:raise ValueError('unsupported_message_content')
        blocks=[]
        for block in value:
            kind=block.get('type')
            if kind=='thinking' or (type(kind) is str and kind.startswith('thinking_')):
                redactions+=1;continue
            if kind=='text' and type(block.get('text')) is str:blocks.append(dict(type='text',text=clean(block['text'])))
            elif kind=='toolCall' and all(type(block.get(k)) is str for k in ('id','name')):
                normalized_id=_digest([scope,block['id']]);call_mapping[block['id']]=normalized_id
                blocks.append(dict(type='toolCall',id=normalized_id,name=block['name'],arguments=clean(block.get('arguments',{}))))
            elif kind=='image' and all(type(block.get(k)) is str for k in ('data','mimeType')):
                blocks.append(dict(type='image',data=block['data'],mimeType=block['mimeType']))
            else:raise ValueError('unsupported_message_block')
        return blocks
    try:
        path=Path(path)
        if path.is_symlink():raise ValueError('unsafe_journal')
        with path.open('rb') as stream:raw=stream.read(max_journal_bytes+1)
        if len(raw)>max_journal_bytes:
            return dict(status='deferred',reason='journal_memory_limit',limit=max_journal_bytes,observed_at_least=len(raw),unit='bytes',recovery='Original journal is unchanged; explicitly choose a reviewed parser budget or indexed reader. No truncation admitted.')
        records=[json.loads(line) for line in raw.splitlines() if line.strip()]
        if not records or records[0].get('type')!='session' or records[0].get('version')!=3 or records[0].get('id')!=expected_session_id:raise ValueError('journal_session_mismatch')
        entries=records[1:];by_id={}
        supported={'message','model_change','thinking_level_change','usage','compaction','context_edit','branch_summary','custom','custom_message','label','session_info'}
        for entry in entries:
            if entry.get('type') not in supported:raise ValueError('unsupported_journal_entry')
            key=entry.get('id')
            if type(key) is not str or not key or key in by_id or 'parentId' not in entry:raise ValueError('invalid_journal_entry')
            by_id[key]=entry
        branch=[];cursor=leaf_id;seen=set()
        if type(cursor) is not str or cursor not in by_id:raise ValueError('explicit_leaf_required')
        while cursor is not None:
            if type(cursor) is not str or cursor in seen or cursor not in by_id:raise ValueError('invalid_journal_branch')
            seen.add(cursor);entry=by_id[cursor];branch.append(entry);cursor=entry['parentId']
        branch.reverse();projection=projector(entries,leaf_id);rows=[];mapping=[];projected_sources=set()
        for entry in projection['entries']:
            origin=entry['source_entry_id']
            if origin not in seen:raise ValueError('projection_outside_selected_branch')
            if origin in projected_sources:raise ValueError('duplicate_projected_entry')
            projected_sources.add(origin)
            for index,message in enumerate(entry['messages']):
                key='message:'+_digest([scope,origin,index]);role=message['role']
                if role in ('compactionSummary','branchSummary'):visible=dict(role='memory',content=clean(message['summary']));normalized='memory'
                else:
                    normalized={'toolResult':'tool','custom':'memory'}.get(role,role)
                    if normalized not in ('system','user','assistant','tool','memory'):raise ValueError('unsupported_projected_role')
                    visible=dict(role=normalized,content=content(message['content']))
                if role=='system':
                    for field in ('sections','toolsAdded','toolsRemoved'):
                        if field in message:visible[field]=clean(message[field])
                if role=='assistant':
                    visible['stopReason']=message.get('stopReason')
                    if message.get('errorMessage'):visible['errorMessage']=clean(message['errorMessage'])
                blocks=visible.get('content') if type(visible.get('content')) is list else []
                calls=tuple((b['id'],b['name']) for b in blocks if isinstance(b,dict) and b.get('type')=='toolCall')
                tool_name=message.get('toolName') if role=='toolResult' else None
                result_for=_digest([scope,message['toolCallId']]) if role=='toolResult' else None
                if role=='toolResult':visible.update(toolCallId=result_for,toolName=tool_name,isError=message.get('isError',False))
                details=message.get('details') or {}
                unknown=type(details) is dict and (details.get('environment_result_unknown') is True or details.get('processing_blocked') is True)
                images=type(visible.get('content')) is list and any(b.get('type')=='image' for b in visible['content'])
                rows.append(Message(key,normalized,_encode(visible).decode(),calls=calls,result_for=result_for,tool_name=tool_name,
                                    negative=message.get('isError') is True or message.get('stopReason') in ('error','aborted'),protected=unknown or images or role=='custom'))
                mapping.append(dict(message_id=key,native_entry_id=origin,projected_index=index))
        witness=dict(journal_file=str(path),session_id=expected_session_id,leaf_id=leaf_id,journal_sha256=hashlib.sha256(raw).hexdigest(),branch_sha256=_digest(branch),branch_entries=len(branch),branch_ids_sha256=_digest([e['id'] for e in branch]),
                     projection_sha256=_digest([dict(id=r.id,role=r.role,text=r.text,calls=r.calls,result_for=r.result_for,tool_name=r.tool_name,negative=r.negative,protected=r.protected) for r in rows]),
                     source_mapping=mapping,call_mapping=[dict(native_call_id=k,call_id=v) for k,v in call_mapping.items()],redactions=redactions,projection_source='pinned_sdk' if projector is sdk_projection else 'injected_projector',sdk_index_sha256=projection.get('sdk_index_sha256'),projection_helper_sha256=projection.get('projection_helper_sha256'),active_cursor_verified=False,provider_payload_verified=False)
        snapshot=capture(scope,rows,source_revision=_digest(witness),keep_recent_groups=keep_recent_groups)
        return dict(status='observed',adapter='pi-session-projection/1',runtime_version='1.5.0',witness=witness,conversation=snapshot,installation_authorized=False)
    except subprocess.TimeoutExpired as error:
        return dict(status='deferred',reason='projection_helper_timeout',limit=error.timeout,unit='seconds',installation_authorized=False,recovery='Original journal is unchanged; inspect the read-only helper before explicit retry.')
    except (ValueError,KeyError,TypeError,AttributeError,OSError) as error:
        return dict(status='deferred',reason=str(error) if isinstance(error,ValueError) else type(error).__name__,installation_authorized=False)
