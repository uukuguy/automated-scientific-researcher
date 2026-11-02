"""Bounded, runtime-neutral Context7 documentation lookups, without model calls."""
import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone
from urllib import request, parse, error


class DocumentationError(ValueError):
    def __init__(self, code):
        self.code = code
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
        self.lock = threading.Lock()

    @staticmethod
    def _text(value, maximum):
        if type(value) is not str or not value.strip() or len(value) > maximum:
            raise DocumentationError('invalid_documentation_query')
        return value

    def resolve_library(self, library_name, query):
        return self._call('libs/search', dict(libraryName=self._text(library_name, 120), query=self._text(query, 2000)))

    def query_docs(self, library_id, query):
        if type(library_id) is not str or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:[/@][A-Za-z0-9_.-]+)?', library_id) or any(part in ('.', '..') for part in library_id.split('/')):
            raise DocumentationError('invalid_documentation_library')
        return self._call('context', dict(libraryId=library_id, query=self._text(query, 2000), type='json'))

    def _call(self, endpoint, parameters):
        with self.lock:
            if self.remaining <= 0:
                raise DocumentationError('documentation_call_limit')
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
                        raise DocumentationError('documentation_deadline_exceeded')
                    chunk = response.read1(min(8192, 100001 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                raw = b''.join(chunks)
            if len(raw) > 100000:
                raise DocumentationError('documentation_response_too_large')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise DocumentationError('invalid_documentation_response')
        except error.HTTPError as exc:
            code = {401: 'documentation_auth_required', 403: 'documentation_access_denied',
                    429: 'documentation_rate_limited', 404: 'documentation_not_found'}.get(exc.code, 'documentation_http_error')
            raise DocumentationError(code) from None
        except (OSError, error.URLError, TimeoutError):
            raise DocumentationError('documentation_network_error') from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise DocumentationError('invalid_documentation_response') from None
        return dict(kind='external_documentation', provider='context7', query=parameters['query'],
                    library_id=parameters.get('libraryId'), library_name=parameters.get('libraryName'),
                    source_url=url, retrieved_at=datetime.now(timezone.utc).isoformat(),
                    response_sha256=hashlib.sha256(raw).hexdigest(), response=data,
                    trust='Reference material only; check served version against installed source. Not scientific validation.')
