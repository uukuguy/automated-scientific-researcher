import io
import json
import unittest
from urllib.error import HTTPError
from integrations.research_tools.context7 import Context7Client, DocumentationError


class Response(io.BytesIO):
    status = 200


class Context7Tests(unittest.TestCase):
    def test_exhaustion_reports_configured_observed_remaining_and_recovery(self):
        client=Context7Client(opener=lambda *a,**k:Response(b'{}'),max_calls=1)
        client.resolve_library('pi','SDK')
        with self.assertRaises(DocumentationError) as error:client.resolve_library('pi','SDK')
        details=getattr(error.exception,'details',{})
        self.assertEqual(details.get('configured'),1)
        self.assertEqual(details.get('observed'),2)
        self.assertEqual(details.get('remaining'),0)
        self.assertTrue(details.get('recoverable'))

    def test_unicode_and_deep_json_errors_are_structured_not_uncaught(self):
        client=Context7Client(opener=lambda *a,**k:Response(b'['*2000+b']'*2000))
        for query in ('bad\ud800','valid'):
            with self.subTest(query_ascii=ascii(query)),self.assertRaises(DocumentationError):
                client.resolve_library('pi',query)

    def test_fixed_endpoint_and_returned_version_provenance(self):
        calls = []
        def opener(request, timeout):
            calls.append(request)
            return Response(json.dumps({'version': {'requested': 'v3.5.6', 'resolved': 'v3.5.4'}, 'infoSnippets': []}).encode())
        client = Context7Client(opener=opener)
        result = client.query_docs('/e2niee/pandapower/v3.5.6', 'runpp flat initialization')
        self.assertTrue(calls[0].full_url.startswith('https://context7.com/api/v2/context?'))
        self.assertEqual(result['response']['version']['resolved'], 'v3.5.4')
        self.assertEqual(result['kind'], 'external_documentation')
        self.assertEqual(result['query'], 'runpp flat initialization')
        self.assertNotIn('Authorization', calls[0].headers)

    def test_invalid_input_and_exhausted_budget_do_not_send_requests(self):
        calls = []
        def opener(request, timeout):
            calls.append(request)
            return Response(b'{"results":[]}')
        client = Context7Client(opener=opener, max_calls=1)
        for library in ('https://private.example/a', '/a/../b', '/onlyone'):
            with self.assertRaises(DocumentationError): client.query_docs(library, 'test')
        self.assertFalse(calls)
        client.resolve_library('pandapower', 'runpp')
        with self.assertRaisesRegex(DocumentationError, 'documentation_call_limit'):
            client.resolve_library('pandapower', 'runpp')
        self.assertEqual(len(calls), 1)

    def test_rate_limit_and_oversize_do_not_retry_or_expose_body(self):
        calls = []
        def limited(request, timeout):
            calls.append(request)
            raise HTTPError(request.full_url, 429, 'sensitive provider body', {}, None)
        with self.assertRaisesRegex(DocumentationError, '^documentation_rate_limited$'):
            Context7Client(opener=limited).resolve_library('pi', 'SDK')
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(DocumentationError, 'documentation_response_too_large'):
            Context7Client(opener=lambda *a, **k: Response(b'x'*100001)).resolve_library('pi', 'SDK')

    def test_redirect_is_not_followed(self):
        from integrations.research_tools.context7 import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, 'found', {}, 'https://other.example'))

if __name__ == '__main__': unittest.main()
