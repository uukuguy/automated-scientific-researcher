"""Host-only authenticated material assembly for a frozen isolated panel."""
import json
import hashlib
import os
import stat
from pathlib import Path
from .control import ControlError
from .study import public_materials


def load_panel(config,study):
    panel=config['isolated_panel'];path=Path(panel['path'])
    from asr_supervisor.study import MAX_PAYLOAD_BYTES
    from .study import check_limit
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ControlError('isolated_panel_changed')
        body=stream.read(MAX_PAYLOAD_BYTES+1)
    check_limit('study_payload_limit','isolated_panel_bytes',MAX_PAYLOAD_BYTES,len(body))
    if hashlib.sha256(body).hexdigest()!=panel['sha256']:raise ControlError('isolated_panel_changed')
    data=json.loads(body)
    if type(data) is not dict or set(data)!={'protocol','panels','history'}:
        raise ControlError('invalid_isolated_panel')
    data['case']=public_materials(study)['case']
    return data
