"""Small loopback JSON control API, no external web framework required.

Run: uv run python -m asr_service.http --database /persistent/asr.db
     --credentials /private/tokens.json
Credentials are an operator-managed JSON mapping of bearer tokens to principals.
Only loopback binding is supported; remote access requires an authenticated tunnel.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
from asr_service.control import ControlService, ControlError
from asr_service.contracts import encoded


def strict_json(body):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('duplicate_json_key')
            result[key]=value
        return result
    def constant(value): raise ValueError('nonfinite_json')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=constant)


def make_server(service, *, host='127.0.0.1', port=8765):
    if host not in ('127.0.0.1','::1','localhost'): raise ValueError('loopback_required')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self): self.handle_api()
        def do_POST(self): self.handle_api()
        def handle_api(self):
            try:
                url=urlsplit(self.path)
                parts=[unquote(p) for p in url.path.strip('/').split('/')]
                if len(parts)<4 or parts[:2]!=['v1','projects']: raise ControlError('not_found')
                project=parts[2]
                auth=self.headers.get('Authorization','')
                token=auth[7:] if auth.startswith('Bearer ') else ''
                service._auth(token,project)
                body={}
                if self.command=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=1048576: raise ValueError('invalid_body_length')
                    if self.headers.get_content_type()!='application/json': raise ValueError('json_required')
                    body=strict_json(self.rfile.read(length))
                    if type(body) is not dict: raise ValueError('object_required')
                route=parts[3:]
                if self.command=='GET' and route==['events']:
                    result=service.events(token,project,int(parse_qs(url.query).get('after',['0'])[0]))
                elif self.command=='GET' and len(route)==2 and route[0]=='runs':
                    result=service.get_run(token,project,route[1])
                elif self.command=='GET' and route==['dispatch']:
                    result=service.pending_dispatch(token,project)
                elif self.command=='GET' and len(route)==3 and route[0]=='references':
                    result=service.get_reference(token,project,route[1],route[2])
                elif len(route)==3 and route[0]=='runs' and route[2]=='findings':
                    result=service.findings(token,project,route[1]) if self.command=='GET' else service.publish_finding(token,project,route[1],**body)
                elif self.command=='POST' and route==['contracts']:
                    result=service.publish_contract(token,project,**body)
                elif self.command=='POST' and route==['runs']:
                    result=service.create_run(token,project,**body)
                elif self.command=='POST' and len(route)==3 and route[0]=='runs' and route[2]=='trials':
                    result=service.submit_trial(token,project,route[1],**body)
                elif self.command=='POST' and len(route)==4 and route[0]=='runs' and route[2:] == ['runtime','claim']:
                    result=service.claim_runtime(token,project,route[1],**body)
                elif self.command=='POST' and len(route)==4 and route[0]=='runs' and route[2:] == ['runtime','release']:
                    result=service.release_runtime(token,project,route[1],**body)
                elif self.command=='POST' and len(route)==3 and route[0]=='runs' and route[2]=='activities':
                    result=service.admit_activity(token,project,route[1],**body)
                elif self.command=='POST' and len(route)==3 and route[0]=='runs' and route[2]=='commands':
                    result=service.command(token,project,route[1],**body)
                elif self.command=='POST' and len(route)==2 and route[0]=='references':
                    result=service.register_reference(token,project,route[1],**body)
                else: raise ControlError('not_found')
                self.respond(200,result)
            except (ValueError,TypeError,KeyError) as exc:
                code=getattr(exc,'code',str(exc))
                status=401 if code=='unauthorized' else 403 if code=='forbidden' else 404 if code in ('not_found','run_not_found','contract_not_found','reference_not_found') else 409 if code in ('revision_conflict','idempotency_conflict','admission_closed','budget_exhausted') else 400
                self.respond(status,{'error':code})
            except Exception:
                self.respond(500,{'error':'internal_error'})
        def respond(self,status,result):
            body=encoded(result).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(body)
    return ThreadingHTTPServer((host,port),Handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True)
    parser.add_argument('--credentials',required=True)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    service=ControlService(args.database,credentials=strict_json(Path(args.credentials).read_text()))
    with make_server(service,port=args.port) as server:
        try: server.serve_forever()
        except KeyboardInterrupt: pass

if __name__=='__main__': main()
