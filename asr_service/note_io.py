"""Detached immutable-note reads, reusable by notes and context installation."""
import hashlib
from asr_context.notes import NoteStore
from .contracts import encoded
from .context_io import verify
from .control import ControlError


class PreparedStore:
    def __init__(self,service,project,run,owner):
        scope=encoded([project,run,owner])
        self.store=NoteStore(service.path.parent/'research-notes'/hashlib.sha256(scope.encode()).hexdigest(),scope=scope)
        self.notes={}

    def load(self,revision):
        # NoteStore validates revision syntax before constructing its path.
        from asr_context.notes import _revision
        _revision(revision)
        path=self.store.directory/f'{revision}.json'
        self.notes[revision]=verify(str(path),lambda:self.store.read(revision))
        return self.notes[revision].value

    def read(self,revision):
        if revision not in self.notes:raise ControlError('note_sources_changed')
        self.check()
        return self.notes[revision].value

    def check(self):
        try:
            for note in self.notes.values():note.check()
        except (ControlError,OSError):raise ControlError('note_sources_changed') from None


def accepted(service,project,run,subject):
    """Capture the current head and its attachments without a write transaction."""
    from .note_artifacts import prepare
    import json
    with service._connect() as db:
        from .organization import member
        member(db,project,run,subject)
        row=db.execute('SELECT revision FROM asr_note_heads WHERE project=? AND run=? AND owner=?',(project,run,subject)).fetchone()
        if not row:raise ControlError('context_note_required')
        store=PreparedStore(service,project,run,subject);note=store.load(row[0])
        refs=[json.loads(ref['id'][len('artifact:'):]) for ref in note['sources'] if ref['id'].startswith('artifact:')]
        artifacts=prepare(db,service,project,run,refs)
    return dict(head=row[0],store=store,artifacts=artifacts)


def capture(service,project,run,subject):
    # Defer failures to the existing transactional admission/installation receipt.
    try:return accepted(service,project,run,subject)
    except (ValueError,OSError) as error:return dict(error=error)


def check(prepared,db):
    if prepared is None:raise ControlError('context_note_verification_required')
    if 'error' in prepared:raise prepared['error']
    prepared['store'].check()
    prepared['artifacts'].check(db,json_references(prepared))


def json_references(prepared):
    import json
    return json.loads(prepared['artifacts'].references)
