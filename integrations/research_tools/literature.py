"""Bounded, runtime-neutral Crossref bibliographic metadata search.

Official API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
Parameters: https://github.com/CrossRef/rest-api-doc (query.bibliographic, rows,
select). No model, API key, subscription fallback, retry, DOI resolution or
full-text retrieval. Returned metadata is external and scientifically unverified.

The default transport has a five-second socket timeout, a checked read deadline,
and a 256 KiB response cap. A caller requiring a hard whole-tool deadline must
also supervise the operation: OS DNS resolution is not bounded by urllib's socket
setting. ``opener`` is a trusted test/host injection point, never a tool argument.
"""
from datetime import datetime, timezone
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = 'https://api.crossref.org/works'
TIMEOUT_SECONDS = 5
MAX_BYTES = 256 * 1024
MAX_QUERY_CHARACTERS = 512
SELECT_FIELDS = 'DOI,title,author,published,issued,URL'


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


_ERRORS = {
    'invalid_query': 'Provide 1–512 characters of plain bibliographic search text.',
    'invalid_limit': 'The result limit must be an integer from 1 through 5.',
    'redirect_blocked': 'Crossref redirected the request; no redirect was followed.',
    'rate_limited': 'Crossref rate limited this request; no retry was made.',
    'provider_unavailable': 'Crossref is unavailable; no retry was made.',
    'provider_rejected': 'Crossref rejected the request; no retry was made.',
    'timeout': 'Crossref exceeded the configured transport deadline.',
    'network_error': 'The Crossref request could not be completed.',
    'response_too_large': 'Crossref returned more than the allowed metadata size.',
    'invalid_response': 'Crossref returned unsupported or malformed metadata.',
}


class _ResponseError(ValueError):
    pass


def _result(*, results=None, error=None):
    return dict(schema_version='asr-literature-search/1', ok=error is None,
                source='crossref', content_kind='metadata_only',
                notice='External bibliographic metadata only; no paper text was read or scientific claim validated.',
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                results=[] if results is None else results,
                error=None if error is None else dict(code=error, message=_ERRORS[error],
                    retryable=error in ('rate_limited','provider_unavailable','timeout','network_error')))


def _http_error(status):
    if 300 <= status < 400:
        return 'redirect_blocked'
    if status == 429:
        return 'rate_limited'
    return 'provider_unavailable' if status >= 500 else 'provider_rejected'


def _read(response, deadline):
    content_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    encoding = response.headers.get('Content-Encoding', 'identity').strip().lower()
    if content_type != 'application/json' or encoding not in ('', 'identity'):
        raise _ResponseError('invalid_response')
    declared = response.headers.get('Content-Length')
    if declared is not None:
        try:
            length = int(declared)
        except (TypeError, ValueError):
            raise _ResponseError('invalid_response') from None
        if length < 0:
            raise _ResponseError('invalid_response')
        if length > MAX_BYTES:
            raise _ResponseError('response_too_large')
    body = bytearray()
    # HTTPResponse.read1 makes one underlying read instead of waiting for a full
    # chunk while a peer trickles bytes. Check the total read deadline each time.
    read = getattr(response, 'read1', response.read)
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError
        chunk = read(min(8192, MAX_BYTES + 1 - len(body)))
        if not chunk:
            break
        body.extend(chunk)
        if len(body) > MAX_BYTES:
            raise _ResponseError('response_too_large')
    if time.monotonic() >= deadline:
        raise TimeoutError
    return body


def _text(value, limit=512):
    if not isinstance(value, str):
        return None
    value = ' '.join(re.sub(r'[\x00-\x1f\x7f]', ' ', value).split())
    return value[:limit] or None


def _metadata(item):
    if not isinstance(item, dict):
        raise _ResponseError('invalid_response')
    # Identifiers must never be truncated or have interior characters changed:
    # that could manufacture a citation to a different work.
    doi = item.get('DOI')
    doi = doi.strip() if isinstance(doi, str) else None
    if doi is not None and (len(doi) > 256 or not re.fullmatch(r'10\.\d{4,9}/[^\s<>\x00-\x1f\x7f]+', doi)):
        doi = None
    titles = item.get('title')
    title = _text(titles[0]) if isinstance(titles, list) and titles else None
    authors = []
    source_authors = item.get('author')
    if isinstance(source_authors, list):
        for author in source_authors[:20]:
            if not isinstance(author, dict):
                continue
            name = _text(author.get('name'), 256)
            if name is None:
                name = _text(' '.join(filter(None, (_text(author.get('given'), 128), _text(author.get('family'), 128)))), 256)
            if name:
                authors.append(name)
    year = None
    for kind in ('published', 'issued'):
        date = item.get(kind)
        parts = date.get('date-parts') if isinstance(date, dict) else None
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            candidate = parts[0][0]
            if type(candidate) is int and 0 < candidate <= 9999:
                year = candidate
                break
    # Provide a canonical citation URL, not an arbitrary deposited URL. It is
    # returned as metadata only and is never requested by this client.
    url = 'https://doi.org/' + quote(doi, safe='/') if doi else None
    return dict(doi=doi, title=title, authors=authors, year=year, url=url)


def search(query, limit=5, *, opener=None):
    """Search one public Crossref works page; return a JSON-safe result/error.

    ``query`` is bibliographic text, never an endpoint or URL to fetch. Network
    errors expose static codes only. Missing metadata stays null/empty. A true
    retryable flag is advisory to the caller; this function never retries.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARACTERS:
        return _result(error='invalid_query')
    if any(ord(character) < 32 or ord(character) == 127 for character in query):
        return _result(error='invalid_query')
    try:
        query.encode('utf-8')
    except UnicodeEncodeError:
        return _result(error='invalid_query')
    if type(limit) is not int or not 1 <= limit <= 5:
        return _result(error='invalid_limit')
    url = ENDPOINT + '?' + urlencode({'query.bibliographic':query.strip(), 'rows':limit, 'select':SELECT_FIELDS})
    request = Request(url, headers={'Accept':'application/json', 'Accept-Encoding':'identity',
                                  'User-Agent':'ASR-Literature-Metadata/1 (+https://www.crossref.org/documentation/retrieve-metadata/rest-api/)'})
    deadline = time.monotonic() + TIMEOUT_SECONDS
    try:
        transport = build_opener(_NoRedirect()) if opener is None else opener
        with transport.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.geturl() != url:
                return _result(error='redirect_blocked')
            if response.status != 200:
                return _result(error=_http_error(response.status))
            body = _read(response, deadline)
        def reject_constant(value):
            raise ValueError('nonfinite_json')
        payload = json.loads(body, parse_constant=reject_constant)
        message = payload.get('message') if isinstance(payload, dict) else None
        if not isinstance(payload, dict) or payload.get('status') != 'ok' or not isinstance(message, dict) or not isinstance(message.get('items'), list):
            return _result(error='invalid_response')
        return _result(results=[_metadata(item) for item in message['items'][:limit]])
    except HTTPError as error:
        status = error.code
        error.close()
        return _result(error=_http_error(status))
    except TimeoutError:
        return _result(error='timeout')
    except URLError as error:
        return _result(error='timeout' if isinstance(error.reason, TimeoutError) else 'network_error')
    except _ResponseError as error:
        return _result(error=str(error))
    except OSError:
        return _result(error='network_error')
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return _result(error='invalid_response')
