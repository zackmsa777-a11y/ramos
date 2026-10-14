"""Native HTTP/TLS acceptance against controlled loopback servers."""
import os
import json
from pathlib import Path
import subprocess
import time
import unittest
import test_ramos as support
from test_libraries import BOOTSTRAP
import test_cli_streams as streams
from http_fixture import Fixture


def build(test,body):
    test.standard_library()
    result=test.build('weave "stdlib/http.ramos"\nfn main() {\n'+body+'\n}', '--force')
    test.assertEqual(result.returncode,0,result.stderr)

def fixture(test,tls=False):
    value=Fixture(test.directory,tls=tls);test.addCleanup(value.close);return value

PRINT='print(response.code)\nprint(response.status)\nprint(buffer_len(response.body))\nstdout(response.body)'
GET='let response = http_get(string(arg(1)), array(string, 0, s""), 1000)\n'+PRINT

@unittest.skipIf(BOOTSTRAP,'retained seed has no HTTP intrinsic')
class HTTPTests(unittest.TestCase):
    setUp=support.RamosTests.setUp
    build=support.RamosTests.build
    standard_library=streams.StreamTests.standard_library
    run_native=streams.StreamTests.run_native
    native_path=staticmethod(str)

    def test_http_get_binary_empty_status_chunked_and_redirect(self):
        build(self,GET);f=fixture(self)
        for path,code,data in [('/',200,b'hello\0world\xff'),('/empty',204,b''),('/auth',401,b'{"error":"unauthorized"}'),('/redirect',302,b'redirect'),('/chunked',200,b'abcde')]:
            with self.subTest(path=path):
                r=self.run_native(f.url(path));self.assertEqual(r.returncode,0,r.stderr)
                self.assertEqual(r.stdout,f'{code}\n0\n{len(data)}\n'.encode()+data)
        self.assertEqual([r[1] for r in f.requests],['/','/empty','/auth','/redirect','/chunked'])

    def test_http_post_headers_query_and_binary_body(self):
        build(self,'''let headers = array(string, 2, s"")
headers[0] = s"Content-Type: application/json"
headers[1] = s"Authorization: Bearer fixture-token"
let response = http_post(string(arg(1)), headers, "a\\0b مرحبا", 1000)
'''+PRINT)
        f=fixture(self);data='a\0b مرحبا'.encode();r=self.run_native(f.url('/echo?query=1'))
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout,f'200\n0\n{len(data)}\n'.encode()+data)
        method,path,headers,body=f.requests[0]
        self.assertEqual((method,path,body),('POST','/echo?query=1',data))
        self.assertEqual(headers['Authorization'],'Bearer fixture-token')
        self.assertEqual(headers['Content-Type'],'application/json')

    def test_https_trusted_name_check_and_untrusted_rejection(self):
        build(self,GET);f=fixture(self,tls=True);env=f.env()
        r=self.run_native(f.url('/',f.https,'localhost'),env=env)
        self.assertEqual((r.returncode,r.stdout),(0,b'200\n0\n12\nhello\0world\xff'),r.stderr)
        for url in [f.url('/',f.https,'127.0.0.1'),f.url('/',f.untrusted,'localhost')]:
            r=self.run_native(url,env=env)
            self.assertEqual((r.returncode,r.stdout),(0,b'0\n-13\n0\n'),r.stderr)
        self.assertEqual(len(f.requests),1,'Invalid certificate/name must fail before sending the HTTP request')

    def test_http_timeout_and_connection_failure(self):
        build(self,GET.replace('1000','100'));f=fixture(self)
        start=time.monotonic();r=self.run_native(f.url('/slow'))
        diagnostic=r.stderr
        if os.name=='nt' and r.stdout!=b'0\n-110\n0\n':
            from winhttp_timeout_probe import probe
            diagnostic=repr([probe(f.url('/slow'),100),probe(f.url('/stall'),100)])
        self.assertEqual((r.returncode,r.stdout),(0,b'0\n-110\n0\n'),diagnostic)
        self.assertLess(time.monotonic()-start,3)
        # A just-closed fixture port provides a deterministic refused connection.
        port=f.http.server_port;f.http.shutdown();f.http.server_close()
        r=self.run_native(f'http://127.0.0.1:{port}/')
        self.assertEqual((r.returncode,r.stdout),(0,b'0\n-111\n0\n'),r.stderr)

    def test_http_response_limit_and_exact_capacity(self):
        build(self,GET.replace('1000','5000'));f=fixture(self)
        r=self.run_native(f.url('/large'));self.assertEqual((r.returncode,r.stdout),(0,b'0\n-27\n0\n'),r.stderr)
        r=self.run_native(f.url('/exact'));self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(r.stdout,b'200\n0\n1048568\n'+b'x'*1048568)

    def test_http_packet_validation_no_network_and_private_types(self):
        build(self,GET)
        for url in ['file:///etc/passwd','ftp://localhost/','http://user:password@localhost/','http://localhost/#fragment','http://localhost/\\path','http://localhost/\npath']:
            r=self.run_native(url);self.assertEqual((r.returncode,r.stdout),(0,b'0\n-22\n0\n'),r.stderr)
        # Rebuild using the existing stdlib snapshot, with a header injection attempt.
        r=self.build('weave "stdlib/http.ramos"\nfn main() { let h = array(string, 1, s"X-Test: ok\\r\\nInjected: yes")\nlet response = http_get(s"http://127.0.0.1:1/", h, 1000)\n'+PRINT+'\n}', '--force')
        self.assertEqual(r.returncode,0,r.stderr)
        r=self.run_native();self.assertEqual(r.stdout,b'0\n-22\n0\n',r.stderr)
        for call in ['_http_request(1, "", "")','_http_request("", "")','_http_request("", "", true)']:
            self.output.unlink(missing_ok=True)
            r=self.build('fn main() { print('+call+') }','--force');self.assertNotEqual(r.returncode,0)
            self.assertFalse(self.output.exists())

    def test_http_private_packet_bounds_and_disabled_gtk(self):
        result=self.build('fn main() {\nlet out = buffer(8)\nprint(_http_request(buffer(0), buffer(0), out))\nprint(io_error())\nprint(_http_request(buffer(34), buffer(0), out))\nprint(io_error())\nlet short = buffer(7)\nprint(_http_request(buffer(34), buffer(0), short))\nprint(io_error())\n}', '--force')
        self.assertEqual(result.returncode,0,result.stderr)
        result=self.run_native()
        self.assertEqual((result.returncode,result.stdout),(0,b'-22\n-22\n-22\n-22\n-22\n-22\n'),result.stderr)
        if os.name=='posix' and not os.environ.get('RAMOS_WINDOWS_COMPILER'):
            result=self.build('fn main() { print(_http_request(buffer(0), buffer(0), buffer(8)))\nprint(_gui_open("x", 100, 100)) }','--force')
            self.assertEqual(result.returncode,0,result.stderr)
            result=self.run_native()
            self.assertEqual((result.returncode,result.stdout),(0,b'-22\n-38\n'),result.stderr)
            # The combined GTK+HTTP import table must resolve both slot sets.
            self.standard_library()
            result=self.build('weave "stdlib/http.ramos"\nfn main() { let response = http_get(string(arg(1)), array(string, 0, s""), 1000)\nprint(response.code)\nprint(_gui_open("HTTP GTK", 320, 240))\nprint(_gui_close()) }','--force','--gui')
            self.assertEqual(result.returncode,0,result.stderr)
            f=fixture(self)
            result=subprocess.run(['xvfb-run','-a',str(self.output),f.url()],capture_output=True,timeout=20,
                                  env=dict(os.environ,NO_AT_BRIDGE='1',GDK_BACKEND='x11'))
            self.assertEqual((result.returncode,result.stdout),(0,b'200\n0\n0\n'),result.stderr)

    def test_http_repeated_requests_collect_and_release(self):
        build(self,'''for i in 0..40 {
let response = http_get(string(arg(1)), array(string, 0, s""), 1000)
if response.code != 200 || response.status != 0 { exit(1) }
}
collect()
print(memory_used())''')
        f=fixture(self);r=self.run_native(f.url())
        self.assertEqual(r.returncode,0,r.stderr);self.assertLess(int(r.stdout),262144)
        self.assertEqual(len(f.requests),40)

    def test_http_api_post_example(self):
        self.standard_library()
        code=(support.ROOT/'examples/api_post.ramos').read_text(encoding='utf-8').replace('../stdlib/','stdlib/')
        r=self.build(code,'--force');self.assertEqual(r.returncode,0,r.stderr)
        request=self.directory/'request.json';data='{"input":"مرحبا 🌍"}'.encode();request.write_bytes(data)
        f=fixture(self,tls=True);env=dict(f.env(),RAMOS_API_TOKEN='fixture-token')
        r=self.run_native(f.url('/echo',f.https,'localhost'),self.native_path(request),env=env)
        self.assertEqual((r.returncode,r.stdout),(0,data),r.stderr)
        self.assertEqual(f.requests[0][2]['Authorization'],'Bearer fixture-token')
        target='windows' if os.name=='nt' else 'linux'
        report={'target':target,'backend':'WinHTTP' if os.name=='nt' else 'libcurl',
                'fixture':'controlled loopback HTTPS with a temporary trusted test CA',
                'ramos_post_example':True,'unicode_json_response_bytes':True,
                'authorization_header':True,'external_helper_process':False,
                'scope':'Native API client acceptance. No paid or live LLM provider was contacted.'}
        (support.ROOT/'build'/f'{target}-http-proof.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
