import multiprocessing
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from evoagent_v3.llm import ChatCompletionsClient, LLMResult
from evoagent_v3.workflow import WorkflowEngine
from evoagent_v3.diff_parser import parse_unified_diff
from evoagent_v3.gates import validate_findings
from evoagent_v3.models import normalize_report

DIFF = 'diff --git a/a.py b/a.py\n--- /dev/null\n+++ b/a.py\n@@ -0,0 +1 @@\n+danger(user)\n'
FINDING = dict(rule_id='R', title='Unchecked input', path='a.py', line=1,
               evidence='danger(user)', explanation='User input reaches danger without validation.')

class IntegrityTests(unittest.TestCase):
    def test_synthesis_cannot_drop_or_replace_approved_finding(self):
        class Model:
            model = 'test'
            def complete_json(self, system, user):
                if 'Lead producing the final review' in system:
                    return LLMResult({'summary':'summary', 'findings':[]})
                return LLMResult({
                    'action': 'final',
                    'result': {'summary': 'reviewed', 'findings': [dict(FINDING)]},
                })
        report, _ = WorkflowEngine(Model()).review('task','o/r',1,DIFF,'collaborative')
        self.assertEqual(1,len(report['findings']))
        self.assertEqual(FINDING['explanation'],report['findings'][0]['explanation'])

    def test_prose_containing_code_is_not_exact_evidence(self):
        bad = dict(FINDING,evidence='I saw danger(user) in the tool')
        gate = validate_findings([bad],parse_unified_diff(DIFF))
        self.assertEqual('evidence_not_on_added_line',gate.rejected[0]['reason'])

    def test_missing_explanation_is_not_silently_published(self):
        gate = validate_findings([dict(FINDING,explanation='')],parse_unified_diff(DIFF))
        self.assertEqual('missing_explanation',gate.rejected[0]['reason'])

    def test_empty_report_does_not_claim_confirmed_vulnerabilities(self):
        report=normalize_report({'summary':'Confirmed severe vulnerabilities'},'o/r',1,'baseline',[])
        self.assertNotEqual('Confirmed severe vulnerabilities',report['summary'])
        self.assertEqual('Confirmed severe vulnerabilities',report['model_summary'])

    def test_trickling_response_has_hard_deadline_and_no_worker_leak(self):
        started = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200)
                self.send_header('Content-Length','100000')
                self.end_headers()
                started.set()
                try:
                    for _ in range(100):
                        self.wfile.write(b' ')
                        self.wfile.flush()
                        time.sleep(0.03)
                except (BrokenPipeError,ConnectionResetError): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        before={p.pid for p in multiprocessing.active_children()}
        clock=time.monotonic()
        try:
            client=ChatCompletionsClient(f'http://127.0.0.1:{server.server_port}', 'test', 'test', 0.8)
            with self.assertRaisesRegex(TimeoutError,'total request deadline'):
                client.complete_json('JSON','test')
            self.assertTrue(started.is_set())
            self.assertLess(time.monotonic()-clock,3)
            self.assertEqual(before,{p.pid for p in multiprocessing.active_children()})
        finally:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    unittest.main()
