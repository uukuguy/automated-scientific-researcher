"""Immutable notes. The caller owns the accepted revision, not this store.

Scope is a binding check, not authentication. Supply only authorized sources;
role filtering is a further guard and does not replace OS/service boundaries.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from . import Material, material_digest, _encode


def _revision(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None:
        raise ValueError('invalid_note_revision')
    return value


class NoteStore:
    def __init__(self, root, *, scope):
        if type(scope) is not str or not scope:raise ValueError('invalid_note_scope')
        self.root=Path(root);self.scope=scope
        if self.root.is_symlink():raise ValueError('unsafe_note_directory')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.directory=self.root/'revisions'
        if self.directory.is_symlink():raise ValueError('unsafe_note_directory')
        self.directory.mkdir(exist_ok=True,mode=0o700)
        self._check_directory()

    def _check_directory(self):
        if self.root.is_symlink() or self.directory.is_symlink():raise ValueError('unsafe_note_directory')

    def save(self, text, *, sources, parent=None):
        if type(text) is not str or not text.strip():raise ValueError('invalid_note_text')
        if parent is not None:self.read(parent)
        rows=list(sources)
        if any(type(r) is not Material for r in rows) or len({r.id for r in rows})!=len(rows):
            raise ValueError('invalid_note_sources')
        record=dict(schema='asr-research-note/1',scope=self.scope,parent=parent,text=text,
                    sources=[dict(id=r.id,revision=r.revision,sha256=material_digest(r)) for r in rows])
        body=_encode(record);revision=hashlib.sha256(body).hexdigest()
        self._check_directory();path=self.directory/f'{revision}.json'
        descriptor,temporary=tempfile.mkstemp(dir=self.directory,prefix='.note-')
        try:
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(body);stream.flush();os.fsync(stream.fileno())
            try:os.link(temporary,path)  # Publish without overwriting an existing revision.
            except FileExistsError:pass
            self.read(revision)
            directory_fd=os.open(self.directory,os.O_RDONLY)
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
        finally:Path(temporary).unlink(missing_ok=True)
        return revision

    def read(self, revision):
        self._check_directory();path=self.directory/f'{_revision(revision)}.json'
        if path.is_symlink():raise ValueError('unsafe_note_file')
        try:body=path.read_bytes();record=json.loads(body)
        except (OSError,ValueError):raise ValueError('note_unavailable_or_corrupt') from None
        if hashlib.sha256(body).hexdigest()!=revision or type(record) is not dict or set(record)!={'schema','scope','parent','text','sources'}:
            raise ValueError('note_corrupt')
        if record['scope']!=self.scope or record['schema']!='asr-research-note/1':raise ValueError('note_scope_or_schema_mismatch')
        if type(record['text']) is not str or not record['text'].strip() or type(record['sources']) is not list:
            raise ValueError('note_corrupt')
        if record['parent'] is not None:_revision(record['parent'])
        for ref in record['sources']:
            if type(ref) is not dict or set(ref)!={'id','revision','sha256'} or any(type(ref[k]) is not str or not ref[k] for k in ref):raise ValueError('note_corrupt')
            _revision(ref['sha256'])
        if len({r['id'] for r in record['sources']})!=len(record['sources']):raise ValueError('note_corrupt')
        return record


def restore(store, *, accepted_revision, materials, role):
    """Verify sources before exposing the caller-selected accepted note.

    Changed sources defer restoration for explicit review. No automatic rewriting
    of the note, authority update or scientific validity claim is performed.
    """
    if type(role) is not str or not role:raise ValueError('invalid_role')
    if accepted_revision is None:return dict(status='empty',material=None)
    note=store.read(accepted_revision)
    rows=list(materials)
    if any(type(r) is not Material for r in rows) or len({r.id for r in rows})!=len(rows):raise ValueError('invalid_restore_sources')
    visible={r.id:r for r in rows if not r.roles or role in r.roles}
    for ref in note['sources']:
        source=visible.get(ref['id'])
        if source is None:return dict(status='deferred',reason='source_unavailable',note_revision=accepted_revision)
        if source.revision!=ref['revision'] or material_digest(source)!=ref['sha256']:
            return dict(status='deferred',reason='source_changed',note_revision=accepted_revision)
    material=Material('note:'+accepted_revision,accepted_revision,note['text'],
                      citations=tuple(r['id'] for r in note['sources']),roles=(role,),protected=True)
    return dict(status='ready',note_revision=accepted_revision,material=material)
