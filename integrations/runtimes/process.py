"""OS process birth identity and conservative local runtime reconciliation.

No signal is sent to a reused PID or a process from another host. Missing birth
identity cannot authorize releasing a reservation. A process group must be the
root's own group (created with start_new_session=True).
"""
import ctypes
import ctypes.util
from functools import lru_cache
import re
from pathlib import Path
import os
import platform
import signal
import subprocess
import time


@lru_cache(maxsize=1)
def _boot_id():
    if platform.system()=='Linux':return Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    value=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.boottime'],text=True)
    match=re.search(r'sec = (\d+), usec = (\d+)',value)
    if not match:raise RuntimeError('boot_identity_unavailable')
    return ':'.join(match.groups())


def identify(pid):
    if type(pid) is not int or pid<=1: raise ValueError('invalid_process_id')
    if platform.system()=='Darwin':
        class BsdInfo(ctypes.Structure):
            _fields_=[(name,ctypes.c_uint32) for name in ('flags','status','xstatus','pid','ppid','uid','gid','ruid','rgid','svuid','svgid','rfu')]+[
                ('comm',ctypes.c_char*16),('name',ctypes.c_char*32)]+[(name,ctypes.c_uint32) for name in ('nfiles','pgid','pjobc','tdev','tpgid')]+[
                ('nice',ctypes.c_int32),('start_sec',ctypes.c_uint64),('start_usec',ctypes.c_uint64)]
        lib=ctypes.CDLL(ctypes.util.find_library('proc'));info=BsdInfo()
        size=lib.proc_pidinfo(pid,3,0,ctypes.byref(info),ctypes.sizeof(info))
        if size==0:
            try: os.kill(pid,0)
            except ProcessLookupError:return None
            state=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
            if not state or state.startswith('Z'): return None
            raise RuntimeError('process_identity_unavailable')
        if size!=ctypes.sizeof(info) or info.pid!=pid: raise RuntimeError('process_identity_unavailable')
        if info.status==5:return None  # SZOMB: exited, waiting to be reaped.
        birth=f'{info.start_sec}.{info.start_usec:06d}';pgid=info.pgid
    elif platform.system()=='Linux':
        try: raw=open(f'/proc/{pid}/stat').read()
        except FileNotFoundError:return None
        fields=raw[raw.rfind(')')+2:].split()
        if fields[0]=='Z':return None
        birth=fields[19];pgid=int(fields[2])
    else: raise RuntimeError('unsupported_process_identity_platform')
    return dict(backend='host-process',pid=pid,pgid=pgid,birth=birth,host=platform.node(),boot=_boot_id())


def _members(pgid):
    result=subprocess.run(['ps','-axo','pid=,pgid='],capture_output=True,text=True,check=True)
    members=[]
    for line in result.stdout.splitlines():
        parts=line.split()
        if len(parts)==2 and int(parts[1])==pgid:
            identity=identify(int(parts[0]))
            if identity:members.append(identity)
    return members


def verify_process_exit(identity, *, terminate=False):
    if not isinstance(identity,dict) or set(identity)!={'backend','pid','pgid','birth','host','boot'}:
        raise RuntimeError('process_identity_required')
    if identity['backend']!='host-process' or identity['host']!=platform.node() or identity['boot']!=_boot_id() or identity['pid']!=identity['pgid']:
        raise RuntimeError('process_identity_mismatch')
    current=identify(identity['pid'])
    if current is not None and current!=identity: raise RuntimeError('process_identity_mismatch')
    members=_members(identity['pgid'])
    if current is None and members: raise RuntimeError('unowned_process_group_active')
    terminated=False
    if current:
        if not terminate: raise RuntimeError('process_still_active')
        os.killpg(identity['pgid'],signal.SIGTERM);terminated=True
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if not _members(identity['pgid']):break
            time.sleep(.05)
        remaining=_members(identity['pgid'])
        if remaining:
            # Only signal again while at least one original process survives.
            if not any(x in members for x in remaining):raise RuntimeError('process_identity_mismatch')
            os.killpg(identity['pgid'],signal.SIGKILL)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline and _members(identity['pgid']):time.sleep(.05)
    if _members(identity['pgid']):raise RuntimeError('process_exit_unconfirmed')
    return dict(execution_exited=True,identity=identity,observed_at=time.time(),terminated=terminated)


def reconcile_process(identity):
    return verify_process_exit(identity,terminate=True)['execution_exited']
