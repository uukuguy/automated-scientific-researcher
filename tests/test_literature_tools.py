"""Crossref transport tests: metadata only, no external/model calls."""
import io
import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from integrations.research_tools.literature import search, MAX_BYTES, TIMEOUT_SECONDS, _NoRedirect


class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'application/json'}

    def geturl(self):
        return self.url


class LiteratureTests(unittest.TestCase):
    def test_every_metadata_cap_has_explicit_loss_and_recovery_metadata(self):
        item={'DOI':'10.1234/'+'x'*300,'title':['t'*600],'author':[{'name':'n'*300}]*22}
        opener,_=self.transport({'status':'ok','message':{'items':[item]*2}})
        result=search('bounded search',limit=1,opener=opener)
        diagnostics=result.get('diagnostics')
        self.assertIsInstance(diagnostics,dict,'metadata caps must not silently omit content')
        affected={entry['field'] for entry in diagnostics['omissions']}
        self.assertTrue({'results','doi','title','authors','authors[0].name'}<=affected)
        self.assertTrue(result['recoverable'])
        self.assertIn('response_bytes',result['configured_caps'])

    def test_invalid_query_reports_observed_and_configured_length(self):
        result=search('x'*513,opener=Mock())
        self.assertEqual(result['error'].get('configured'),512)
        self.assertEqual(result['error'].get('observed'),513)
        self.assertTrue(result['error']['recoverable'])

    def transport(self, payload=None, raw=None):
        raw = json.dumps(payload).encode() if raw is None else raw
        response = Response(raw)
        opener = Mock()
        def open_(request, timeout):
            response.url = request.full_url
            return response
        opener.open.side_effect = open_
        return opener, response

    def test_bounded_metadata_contract_fixed_endpoint_and_encoded_query(self):
        item = dict(DOI='10.1234/power-flow', title=['Power flow'], author=[{'given':'A','family':'Researcher'}],
                    published={'date-parts': [[2024, 3]]}, URL='https://doi.org/10.1234/power-flow',
                    abstract='must not expose full text or abstracts')
        opener, _ = self.transport({'status':'ok','message':{'items':[item]*8}})
        result = search('power flow & rows=999', limit=2, opener=opener)
        self.assertTrue(result['ok'])
        self.assertEqual(result['content_kind'], 'metadata_only')
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(result['results'][0], dict(doi='10.1234/power-flow',title='Power flow',
                         authors=['A Researcher'],year=2024,url='https://doi.org/10.1234/power-flow'))
        request = opener.open.call_args.args[0]
        parsed = urlsplit(request.full_url)
        self.assertEqual((parsed.scheme,parsed.netloc,parsed.path),('https','api.crossref.org','/works'))
        self.assertEqual(parse_qs(parsed.query)['query.bibliographic'], ['power flow & rows=999'])
        self.assertEqual(parse_qs(parsed.query)['rows'], ['2'])
        self.assertEqual(opener.open.call_args.kwargs['timeout'], TIMEOUT_SECONDS)
        self.assertEqual(opener.open.call_count, 1)

    def test_invalid_requests_never_reach_transport(self):
        opener=Mock()
        for query in ('', '   ', 'x'*513, 'unsafe\x00query', None, ['power flow']):
            self.assertEqual(search(query, opener=opener)['error']['code'], 'invalid_query')
        for limit in (0,6,-1,True,1.5,'5'):
            self.assertEqual(search('power flow',limit=limit,opener=opener)['error']['code'],'invalid_limit')
        opener.open.assert_not_called()

    def test_size_content_type_and_malformed_envelope_are_bounded(self):
        opener,response=self.transport(raw=b'x'*(MAX_BYTES+1))
        self.assertEqual(search('power flow',opener=opener)['error']['code'],'response_too_large')
        self.assertTrue(response.closed)
        opener,response=self.transport(raw=b'{}'); response.headers={'Content-Type':'text/html'}
        self.assertEqual(search('power flow',opener=opener)['error']['code'],'invalid_response')
        for payload in ({'message':{'items':[]}}, {'status':'ok','message':{'items':{}}}, {'status':'ok','message':None}):
            opener,_=self.transport(payload)
            self.assertEqual(search('power flow',opener=opener)['error']['code'],'invalid_response')
        opener,_=self.transport(raw=b'['*2000+b']'*2000)
        self.assertEqual(search('power flow',opener=opener)['error']['code'],'invalid_response')

    def test_redirect_and_http_failures_are_safe_and_never_retried(self):
        for status,expected in ((302,'redirect_blocked'),(429,'rate_limited'),(503,'provider_unavailable')):
            opener=Mock(); opener.open.side_effect=HTTPError('https://api.crossref.org/works',status,'private diagnostic',{},None)
            result=search('power flow',opener=opener)
            self.assertEqual(result['error']['code'],expected)
            self.assertNotIn('private diagnostic',str(result))
            self.assertEqual(opener.open.call_count,1)
        opener=Mock();opener.open.side_effect=URLError('private proxy password')
        result=search('power flow',opener=opener)
        self.assertEqual(result['error']['code'],'network_error')
        self.assertNotIn('password',str(result))
        self.assertEqual(opener.open.call_count,1)
        opener=Mock();opener.open.side_effect=TimeoutError('private timeout')
        self.assertEqual(search('power flow',opener=opener)['error']['code'],'timeout')

    def test_changed_final_url_is_rejected_before_body_read(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.status=200;response.geturl.return_value='https://other.example/collect'
        opener=Mock();opener.open.return_value=response
        self.assertEqual(search('power flow',opener=opener)['error']['code'],'redirect_blocked')
        response.read.assert_not_called()

    def test_no_redirect_handler_blocks_all_destinations(self):
        from urllib.request import Request
        handler=_NoRedirect()
        self.assertIsNone(handler.redirect_request(Request('https://api.crossref.org/works'),None,302,'redirect',{},'http://127.0.0.1/private'))

    def test_partial_metadata_is_not_fabricated_and_fields_are_capped(self):
        item={'DOI':'10.1234/minimal','title':['x'*2000],'author':[{'name':'Org'}]*200,'published':{'date-parts':[['not-a-year']]},'URL':'javascript:alert(1)'}
        opener,_=self.transport({'status':'ok','message':{'items':[item]}})
        row=search('power flow',opener=opener)['results'][0]
        self.assertLessEqual(len(row['title']),512)
        self.assertLessEqual(len(row['authors']),20)
        self.assertIsNone(row['year'])
        self.assertEqual(row['url'],'https://doi.org/10.1234/minimal')

    def test_declared_length_encoding_and_read_deadline_fail_closed(self):
        from unittest.mock import patch
        opener,response=self.transport(raw=b'{}')
        response.headers={'Content-Type':'application/json','Content-Length':str(MAX_BYTES+1)}
        self.assertEqual(search('power flow',opener=opener)['error']['code'],'response_too_large')
        opener,response=self.transport(raw=b'{}')
        response.headers={'Content-Type':'application/json','Content-Encoding':'gzip'}
        self.assertEqual(search('power flow',opener=opener)['error']['code'],'invalid_response')
        opener,response=self.transport(raw=b'{}')
        with patch('integrations.research_tools.literature.time.monotonic',side_effect=[0,6]):
            result=search('power flow',opener=opener)
        self.assertEqual(result['error']['code'],'timeout')
        self.assertTrue(response.closed)
        self.assertEqual(opener.open.call_count,1)

    def test_default_transport_does_not_follow_real_local_redirect(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.request import build_opener
        import threading
        paths=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                paths.append(self.path)
                self.send_response(302)
                self.send_header('Location','/must-not-fetch')
                self.send_header('Content-Length','0')
                self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with self.assertRaises(HTTPError) as error:
                build_opener(_NoRedirect()).open('http://127.0.0.1:'+str(server.server_port)+'/start',timeout=2)
            self.assertEqual(error.exception.code,302)
            error.exception.close()
            self.assertEqual(paths,['/start'])
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_long_identifier_is_not_truncated_into_a_different_doi(self):
        item={'DOI':'10.1234/'+('x'*300),'title':['A valid title']}
        opener,_=self.transport({'status':'ok','message':{'items':[item]}})
        row=search('power flow',opener=opener)['results'][0]
        self.assertIsNone(row['doi'])
        self.assertIsNone(row['url'])
