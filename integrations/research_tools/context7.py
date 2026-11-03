"""Bounded, runtime-neutral Context7 documentation lookups, without model calls."""
import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone
from urllib import request, parse, error


CAPS=dict(client_calls_default=8,client_calls_maximum=100,library_name_characters=120,query_characters=2000,library_id_characters=256,response_bytes=100000,socket_timeout_seconds=10)


class DocumentationError(ValueError):
    def __init__(self, code,*,configured=None,observed=None,remaining=None,basis='exact'):
        self.code = code
        self.details=dict(configured=configured,observed=observed,observed_basis=basis,remaining=remaining,
            configured_caps=CAPS,recoverable=True,
            recovery='Keep retrieved references; narrow/correct the query or request an explicitly authorized client cap change. No retry or project-budget reset is automatic.',
            deadline_scope='Socket timeout and checks between reads; DNS or one blocked read may exceed the nominal deadline. Outer runtime supervision is separate.')
        super().__init__(code)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Context7Client:
    def __init__(self, *, opener=None, api_key=None, max_calls=8):
        if type(max_calls) is not int or not 1 <= max_calls <= 100:
            raise DocumentationError('invalid_documentation_limit')
        self.opener = opener or request.build_opener(NoRedirect()).open
        self.api_key = api_key
        self.remaining = max_calls
        self.max_calls=max_calls
        self.lock = threading.Lock()

    def _text(self,value, maximum):
        if type(value) is not str or not value.strip() or len(value) > maximum:
            raise DocumentationError('invalid_documentation_query',configured=maximum,observed=len(value) if isinstance(value,str) else None,remaining=self.remaining)
        try:value.encode('utf-8')
        except UnicodeEncodeError:raise DocumentationError('invalid_documentation_query',configured=maximum,observed=len(value),remaining=self.remaining) from None
        return value

    def resolve_library(self, library_name, query):
        return self._call('libs/search', dict(libraryName=self._text(library_name, 120), query=self._text(query, 2000)))

    def query_docs(self, library_id, query):
        if type(library_id) is not str or len(library_id)>256 or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:[/@][A-Za-z0-9_.-]+)?', library_id) or any(part in ('.', '..') for part in library_id.split('/')):
            raise DocumentationError('invalid_documentation_library',configured=256,observed=len(library_id) if isinstance(library_id,str) else None,remaining=self.remaining)
        return self._call('context', dict(libraryId=library_id, query=self._text(query, 2000), type='json'))

    def _call(self, endpoint, parameters):
        with self.lock:
            if self.remaining <= 0:
                raise DocumentationError('documentation_call_limit',configured=self.max_calls,observed=self.max_calls+1,remaining=0)
            self.remaining -= 1
        url = 'https://context7.com/api/v2/' + endpoint + '?' + parse.urlencode(parameters)
        headers = {'Accept': 'application/json', 'User-Agent': 'ASR-documentation/1'}
        if self.api_key:
            headers['Authorization'] = 'Bearer ' + self.api_key
        deadline = time.monotonic() + 10
        try:
            with self.opener(request.Request(url, headers=headers), timeout=10) as response:
                if response.status != 200:
                    raise DocumentationError('documentation_not_ready')
                chunks = []
                size = 0
                while size <= 100000:
                    if time.monotonic() >= deadline:
                        raise DocumentationError('documentation_deadline_exceeded',configured=10000,observed=max(10000,int((time.monotonic()-(deadline-10))*1000)),remaining=self.remaining)
                    chunk = response.read1(min(8192, 100001 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                raw = b''.join(chunks)
                if time.monotonic()>=deadline:raise DocumentationError('documentation_deadline_exceeded',configured=10000,observed=max(10000,int((time.monotonic()-(deadline-10))*1000)),remaining=self.remaining)
            if len(raw) > 100000:
                raise DocumentationError('documentation_response_too_large',configured=100000,observed=len(raw),remaining=self.remaining,basis='at_least')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise DocumentationError('invalid_documentation_response')
        except error.HTTPError as exc:
            code = {401: 'documentation_auth_required', 403: 'documentation_access_denied',
                    429: 'documentation_rate_limited', 404: 'documentation_not_found'}.get(exc.code, 'documentation_http_error')
            exc.close()
            raise DocumentationError(code,remaining=self.remaining) from None
        except (OSError, error.URLError, TimeoutError):
            raise DocumentationError('documentation_network_error',configured=10000,remaining=self.remaining,basis='unknown') from None
        except DocumentationError:raise
        except (ValueError,UnicodeError,RecursionError):
            raise DocumentationError('invalid_documentation_response',remaining=self.remaining) from None
        return dict(kind='external_documentation', provider='context7', query=parameters['query'],
                    library_id=parameters.get('libraryId'), library_name=parameters.get('libraryName'),
                    source_url=url, retrieved_at=datetime.now(timezone.utc).isoformat(),
                    response_sha256=hashlib.sha256(raw).hexdigest(), response=data,
                    configured_caps=dict(CAPS,client_calls=self.max_calls),remaining_client_calls=self.remaining,
                    original_response_bytes=len(raw),truncated=False,
                    deadline_scope='Socket timeout/checks between reads, not a hard total DNS/request bound; outer ASR deadline applies separately.',
                    trust='Reference material only; check served version against installed source. Not scientific validation.')
