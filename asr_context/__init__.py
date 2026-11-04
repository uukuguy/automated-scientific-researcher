"""Runtime-independent, lossless research context projection.

Original materials remain the authority. This selector performs no model calls,
semantic summarization, execution, persistence or runtime installation.
"""
from dataclasses import dataclass
import hashlib
import json


def _encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


@dataclass(frozen=True)
class Material:
    id: str
    revision: str
    text: str
    references: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    protected: bool = False
    group: str = ''
    complete: bool = True

    def __post_init__(self):
        if any(type(v) is not str or not v for v in (self.id,self.revision,self.text)):
            raise ValueError('invalid_material')
        if any(type(v) is not tuple or any(type(s) is not str or not s for s in v) for v in (self.references,self.roles)):
            raise ValueError('invalid_material_scope')
        if type(self.protected) is not bool or type(self.complete) is not bool or type(self.group) is not str:
            raise ValueError('invalid_material_state')


def compact(materials, *, role, max_bytes):
    """Project authorized source materials, ordered oldest to newest.

    Protect explicit roots and unfinished interactions plus their dependency/group
    closure. Include newer optional closures if the complete serialized result
    fits. Every authorized source stays in the fingerprinted lookup catalog.
    Group IDs must be scoped by the caller to one interaction, not a whole role.
    Access decisions and protected scientific facts are caller-supplied; this
    function cannot infer which fact is important or authorize hidden evidence.
    """
    if type(max_bytes) is not int or max_bytes<1 or type(role) is not str or not role:
        raise ValueError('invalid_capacity_or_role')
    rows=list(materials)
    if any(type(row) is not Material for row in rows) or len({r.id for r in rows})!=len(rows):
        raise ValueError('invalid_or_duplicate_material')
    visible={r.id:r for r in rows if not r.roles or role in r.roles}
    for row in visible.values():
        if any(ref not in visible for ref in row.references):raise ValueError('reference_unavailable')
    groups={}
    for row in visible.values():
        if row.group:groups.setdefault(row.group,set()).add(row.id)

    def closure(roots):
        found=set();pending=list(roots)
        while pending:
            key=pending.pop()
            if key in found:continue
            found.add(key);row=visible[key]
            pending.extend(row.references)
            pending.extend(groups.get(row.group,())-found if row.group else ())
        return found

    required=closure(r.id for r in visible.values() if r.protected or not r.complete)
    catalog=[dict(id=r.id,revision=r.revision,sha256=hashlib.sha256(_encode(dict(
        id=r.id,revision=r.revision,text=r.text,references=r.references,roles=r.roles,
        protected=r.protected,group=r.group,complete=r.complete))).hexdigest()) for r in visible.values()]

    def projection(selected):
        return dict(schema='asr-research-context/1',status='ready',role=role,
                    measurement='serialized_utf8_bytes',capacity=max_bytes,catalog=catalog,
                    protected=[k for k in visible if k in required],
                    retained=[k for k in visible if k in selected],
                    omitted=[k for k in visible if k not in selected],
                    materials=[dict(id=r.id,revision=r.revision,text=r.text,references=list(r.references),
                                    group=r.group,complete=r.complete) for r in visible.values() if r.id in selected])

    selected=set(required);base=projection(selected);size=len(_encode(base))
    if size>max_bytes:
        return dict(schema=base['schema'],status='deferred',reason='protected_material_exceeds_capacity',
                    measurement='serialized_utf8_bytes',capacity=max_bytes,required_bytes=size,
                    protected=base['protected'])
    for key in reversed(visible):
        candidate=selected|closure([key])
        if len(_encode(projection(candidate)))<=max_bytes:selected=candidate
    return projection(selected)
