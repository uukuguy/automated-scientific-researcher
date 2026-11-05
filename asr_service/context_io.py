"""Detached file verification with a short metadata fence at commit time.

Native journals are host-owned. This detects replacement and intervening writes;
it is not a filesystem/SQLite atomic transaction or a privileged-host boundary.
"""
from dataclasses import dataclass
from pathlib import Path
from .control import ControlError


def stamp(path):
    path=Path(path)
    if path.is_symlink():raise ControlError('context_source_changed')
    value=path.stat()
    return (str(path.resolve()),value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns,value.st_mode)


@dataclass(frozen=True)
class VerifiedRead:
    path: str
    version: tuple
    value: object

    def check(self):
        try:current=stamp(self.path)
        except OSError:raise ControlError('context_source_changed') from None
        if current!=self.version:raise ControlError('context_source_changed')
        return self.value


def verify(path,read):
    try:before=stamp(path)
    except OSError:raise ControlError('context_source_changed') from None
    value=read()
    result=VerifiedRead(path,before,value)
    result.check()
    return result
