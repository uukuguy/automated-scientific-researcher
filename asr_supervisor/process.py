"""Trusted local test/debug processes. This backend provides no candidate isolation."""
import os
import signal
import subprocess


class ProcessBackend:
    def __init__(self, command):
        self.command=command
        self.processes={}

    def validate_request(self, request):
        pass

    def create(self, record, path, request):
        # Only trusted test commands; production execution uses DockerBackend.
        return {'name':record['attempt'],'backend':'trusted-process'}

    def start(self, identity, path):
        with (path/'solver.log').open('wb') as stream:
            p=subprocess.Popen(self.command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        self.processes[identity['name']]=p

    def inspect(self, identity):
        p=self.processes.get(identity['name'])
        if p is None: raise RuntimeError('process identity unavailable; reconcile manually')
        code=p.poll()
        return {'running':code is None,'exit_code':code}

    def stop(self, identity):
        p=self.processes.get(identity['name'])
        if p is None: raise RuntimeError('process identity unavailable')
        if p.poll() is None:
            os.killpg(p.pid,signal.SIGKILL)
            p.wait(timeout=5)
        return self.inspect(identity)

    def finalize(self, path, request, status):
        pass
