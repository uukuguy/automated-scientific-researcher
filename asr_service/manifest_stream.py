"""Select one manifest entry while parsing and hashing the entire JSON document.

Memory scales with the parser buffer, nesting and largest scalar, not entry count.
Unknown fields are consumed, never treated as permission or scientific evidence.
"""
import hashlib
import ijson


class _HashReader:
    def __init__(self,stream,chunk_bytes):
        self.stream=stream;self.chunk_bytes=chunk_bytes;self.digest=hashlib.sha256();self.size=0

    def read(self,size=-1):
        body=self.stream.read(self.chunk_bytes if size<0 else min(size,self.chunk_bytes))
        self.digest.update(body);self.size+=len(body)
        return body


def _skip(event,events):
    depth=1 if event[0] in ('start_map','start_array') else 0
    while depth:
        name,_=next(events)
        if name in ('start_map','start_array'):depth+=1
        elif name in ('end_map','end_array'):depth-=1


def _fields(first,events,names):
    if first[0]!='start_map':raise ValueError('invalid_manifest_entry')
    result={}
    while True:
        event,key=next(events)
        if event=='end_map':return result
        if event!='map_key':raise ValueError('invalid_manifest_entry')
        value=next(events)
        if key not in names:_skip(value,events);continue
        if key in result:raise ValueError('ambiguous_manifest_field')
        if value[0] in ('start_map','start_array'):raise ValueError('invalid_manifest_field')
        result[key]=value[1]


def select(path,kind,target,chunk_bytes):
    """Return only identity fields, the selected entry and the full-file digest."""
    headers={};entry=None;seen=set()
    names={'schema','project_id','research_run_id'} if kind=='snapshot' else {'trial_id','execution_attempt_id','status'}
    collection='files' if kind=='snapshot' else 'artifacts'
    try:
        with path.open('rb') as stream:
            reader=_HashReader(stream,chunk_bytes)
            events=iter(ijson.basic_parse(reader,buf_size=chunk_bytes,multiple_values=False,allow_comments=False))
            if next(events)[0]!='start_map':raise ValueError('manifest_object_required')
            while True:
                event,key=next(events)
                if event=='end_map':break
                if event!='map_key':raise ValueError('invalid_manifest')
                value=next(events)
                if key not in names and key!=collection:_skip(value,events);continue
                if key in seen:raise ValueError('ambiguous_manifest_field')
                seen.add(key)
                if key in names:
                    if value[0]!='string':raise ValueError('invalid_manifest_identity')
                    headers[key]=value[1];continue
                if kind=='snapshot':
                    if value[0]!='start_array':raise ValueError('invalid_manifest_files')
                    while True:
                        first=next(events)
                        if first[0]=='end_array':break
                        row=_fields(first,events,{'path','sha256','size'})
                        if row.get('path')==target:
                            if entry is not None:raise ValueError('ambiguous_manifest_target')
                            entry=row
                else:
                    if value[0]!='start_map':raise ValueError('invalid_manifest_artifacts')
                    while True:
                        event,name=next(events)
                        if event=='end_map':break
                        if event!='map_key':raise ValueError('invalid_manifest_artifacts')
                        first=next(events)
                        if name!=target:_skip(first,events);continue
                        if entry is not None:raise ValueError('ambiguous_manifest_target')
                        entry=_fields(first,events,{'sha256','bytes'})
            # Do not stop at the selected entry or root end: validate trailing
            # bytes, UTF-8 and EOF, and include every byte in the digest.
            if next(events,None) is not None:raise ValueError('manifest_trailing_data')
            if set(headers)!=names or collection not in seen or entry is None:raise ValueError('manifest_binding_missing')
            return dict(headers=headers,entry=entry,sha256=reader.digest.hexdigest(),bytes=reader.size)
    except (ijson.JSONError,StopIteration,UnicodeError):
        raise ValueError('invalid_manifest_json') from None
