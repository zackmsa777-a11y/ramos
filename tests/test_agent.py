"""Ramos's bounded API tool loop, against controlled HTTP(S) fixtures only."""
import json
import os
import unittest
import test_ramos as support
import test_cli_streams as streams
from test_libraries import BOOTSTRAP
from http_fixture import Fixture

def answer(text='Tool completed: مرحبا 🌍', finish='stop'):
    return {'choices':[{'finish_reason':finish,'message':{'role':'assistant','content':text}}]}

def tool(name='text_stats', args=None, id='call_fixture'):
    return {'choices':[{'finish_reason':'tool_calls','message':{'role':'assistant','content':None,
        'tool_calls':[{'id':id,'type':'function','function':{'name':name,
        'arguments':json.dumps({'text':'مرحبا 🌍'} if args is None else args,ensure_ascii=False)}}]}}]}

@unittest.skipIf(BOOTSTRAP, 'retained seed has no HTTP or JSON libraries')
class AgentTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library
    run_native = streams.StreamTests.run_native
    native_path = staticmethod(str)

    def agent_build(self):
        self.standard_library()
        source=(support.ROOT/'examples/api_agent.ramos').read_text(encoding='utf-8').replace('../stdlib/','stdlib/')
        r=self.build(source,'--force')
        self.assertEqual(r.returncode,0,r.stderr)

    def agent_fixture(self, responses, tls=False):
        f=Fixture(self.directory,tls=tls);self.addCleanup(f.close)
        f.responses=[(code,data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode())
                     for code,data in responses]
        return f

    def agent_run(self,f,prompt='Count "مرحبا 🌍"\n',token='fixture-token'):
        path=self.directory/'prompt.txt'
        path.write_bytes(prompt.encode() if isinstance(prompt,str) else prompt)
        env=dict(f.env(),RAMOS_API_TOKEN=token)
        return self.run_native(f.url('/chat',f.https,'localhost') if f.https else f.url('/chat'),
                               'fixture-model',self.native_path(path),env=env)

    def test_agent_https_tool_then_final_answer_and_request_schema(self):
        self.agent_build();f=self.agent_fixture([(200,tool()),(200,answer())],tls=True)
        r=self.agent_run(f)
        self.assertEqual((r.returncode,r.stdout,r.stderr),(0,'Tool completed: مرحبا 🌍\n'.encode(),b''))
        self.assertEqual(len(f.requests),2)
        first=json.loads(f.requests[0][3]);second=json.loads(f.requests[1][3])
        self.assertEqual(first['model'],'fixture-model')
        self.assertIs(first['parallel_tool_calls'],False)
        self.assertIs(first['stream'],False)
        self.assertEqual(first['messages'],[{'role':'user','content':'Count "مرحبا 🌍"\n'}])
        self.assertEqual(first['tools'][0]['function']['name'],'text_stats')
        self.assertEqual(second['messages'][1],tool()['choices'][0]['message'])
        result=second['messages'][2]
        self.assertEqual((result['role'],result['tool_call_id']),('tool','call_fixture'))
        self.assertEqual(json.loads(result['content']),{'characters':7,'bytes':15})
        self.assertTrue(all(req[2]['Authorization']=='Bearer fixture-token' for req in f.requests))
        self.assertNotIn(b'fixture-token',r.stdout+r.stderr)

    def test_agent_rejects_invalid_responses_and_unknown_tools(self):
        self.agent_build()
        cases=[(200,b'not JSON'),(200,{}),(200,answer(finish='length')),
               (200,tool(name='run_shell')),(200,tool(args={'text':1})),
               (200,tool(args={'text':'ok','extra':True})),(200,tool(id='')),
               (401,{'error':'fixture-token should never be logged'})]
        for code,data in cases:
            with self.subTest(data=data):
                f=self.agent_fixture([(code,data)]);r=self.agent_run(f)
                self.assertEqual(r.returncode,1,r.stderr)
                self.assertEqual(r.stdout,b'')
                self.assertIn(b'Ramos agent:',r.stderr)
                self.assertNotIn(b'fixture-token',r.stderr)
                self.assertEqual(len(f.requests),1)

    def test_agent_turn_budget_and_utf8_prompt_rejection(self):
        self.agent_build();f=self.agent_fixture([(200,tool())])
        r=self.agent_run(f)
        self.assertEqual((r.returncode,r.stdout),(1,b''),r.stderr)
        self.assertIn(b'8-request limit',r.stderr)
        self.assertEqual(len(f.requests),8)
        f=self.agent_fixture([(200,answer())]);r=self.agent_run(f,b'\xff')
        self.assertEqual(r.returncode,1)
        self.assertIn(b'valid UTF-8',r.stderr)
        self.assertEqual(f.requests,[])
        r=self.agent_run(f,'valid',token='header\ninjection')
        self.assertEqual(r.returncode,1)
        self.assertIn(b'visible ASCII',r.stderr)
        self.assertEqual(f.requests,[])

    def test_agent_direct_answer_and_conversation_cap(self):
        self.agent_build();f=self.agent_fixture([(200,answer(''))])
        r=self.agent_run(f,token='')
        self.assertEqual((r.returncode,r.stdout),(0,b'\n'),r.stderr)
        self.assertNotIn('Authorization',f.requests[0][2])
        f=self.agent_fixture([(200,answer())]);r=self.agent_run(f,'x'*262144)
        self.assertEqual(r.returncode,1)
        self.assertIn(b'256 KiB',r.stderr)
        self.assertEqual(f.requests,[])
