"""Frozen, project-scoped JSON reference registry for trusted control code.

Registration asserts no scientific validity or external artifact availability.
Only registered metadata bytes are hashed; paths are never opened here.
"""
import hashlib
import json
from pathlib import Path
from asr_service.contracts import PolicyStore, PolicyError, encoded


class ReferenceError(ValueError):
    pass


class ReferenceStore(PolicyStore):
    KINDS = frozenset({'problem', 'reference', 'evaluation', 'candidate', 'input_manifest'})

    def __init__(self, path):
        self.path = Path(path)
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS asr_references (
                project TEXT NOT NULL, kind TEXT NOT NULL, digest TEXT NOT NULL,
                document TEXT NOT NULL, PRIMARY KEY(project,kind,digest))''')

    @classmethod
    def _validate(cls, project, kind):
        cls._identity(project, kind)
        if kind not in cls.KINDS:
            raise ReferenceError('unsupported_reference_kind')

    @staticmethod
    def _digest(kind, document):
        return hashlib.sha256(encoded([kind, document]).encode()).hexdigest()

    def register(self, project, kind, document):
        self._validate(project, kind)
        if type(document) is not dict or not document:
            raise ReferenceError('invalid_reference_document')
        try:
            body = encoded(document)
            digest = self._digest(kind, document)
        except PolicyError as exc:
            raise ReferenceError('invalid_reference_document') from exc
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO asr_references VALUES (?,?,?,?)',
                       (project, kind, digest, body))
            # Detect prior corruption instead of silently returning a false ref.
            self.get_in_transaction(db, project, kind, digest)
        return digest

    def get(self, project, kind, digest):
        with self._connect() as db:
            return self.get_in_transaction(db, project, kind, digest)

    @classmethod
    def get_in_transaction(cls, db, project, kind, digest):
        cls._validate(project, kind)
        cls._identity(digest)
        row = db.execute('SELECT document FROM asr_references WHERE project=? AND kind=? AND digest=?',
                         (project, kind, digest)).fetchone()
        if row is None:
            raise ReferenceError('reference_not_found')
        try:
            value = json.loads(row[0])
            if cls._digest(kind, value) != digest:
                raise ReferenceError('reference_corrupt')
        except (ValueError, TypeError, PolicyError) as exc:
            raise ReferenceError('reference_corrupt') from exc
        return value
