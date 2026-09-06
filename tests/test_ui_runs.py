import json
import unittest
from unittest.mock import patch
import config
from runtime import record, observe
from ui_runs import run_test, export_json, export_markdown
from schemas.outputs import LearningAnswer
from llm_client import ModelError, call_model
from modules.learning_explainer import answer_concept_question

class RunExportTests(unittest.TestCase):
    def test_capture_input_output_version_evidence_and_time(self):
        stages = []
        with patch.object(config, 'MOCK_LLM', True):
            result, row = run_test('learning', answer_concept_question, {'question': 'RPA', 'week': 1}, lambda e: stages.append(e['kind']))
        self.assertEqual(row['input']['week'], 1)
        self.assertEqual(row['output'], result.model_dump())
        self.assertEqual(row['variant'], 'C')
        self.assertEqual(row['prompt_version'], 'C-1.3')
        self.assertGreaterEqual(row['elapsed_seconds'], 0)
        self.assertTrue(row['retrieved_evidence'])
        self.assertIn('retrieval_started', stages)
        self.assertIn('model_request', stages)
        self.assertEqual(stages[-1], 'result_ready')
        self.assertTrue(all('elapsed_seconds' in e for e in row['stages']))

    def test_error_is_exportable_without_raw_secret(self):
        def fail(**kwargs):
            raise ModelError('SECRET provider body with credential')
        result, row = run_test('debug', fail, {'activity':'Write Range'})
        self.assertIsNone(result)
        self.assertEqual(row['error']['type'], 'ModelError')
        self.assertNotIn('SECRET', export_json([row]))
        self.assertEqual(row['stages'][-1]['kind'], 'request_failed')

    def test_key_redacted_in_inputs_outputs_and_exports(self):
        key = 'private-config-key-value'
        def echo(**kwargs):
            return LearningAnswer(status='ANSWERED', answer=key + ' sk-123456789xyz')
        with patch.object(config, 'LLM_API_KEY', key):
            _, row = run_test('learning', echo, {'question': key, 'authorization':'Bearer abcd1234'})
            for exported in (export_json([row]), export_markdown([row])):
                self.assertNotIn(key, exported)
                self.assertNotIn('sk-123456789xyz', exported)
                self.assertNotIn('abcd1234', exported)
                self.assertIn('[REDACTED]', exported)

    def test_observer_does_not_leak_to_next_request(self):
        calls = []
        with observe(lambda e: calls.append(e['kind'])):
            record('first')
        record('second')
        self.assertEqual(calls, ['first'])

    def test_raw_prompt_and_response_not_exported(self):
        def answer(**kwargs):
            record('model_request', system='HIDDEN PROMPT', user='RAW INPUT')
            record('model_response', raw='RAW MODEL RESPONSE')
            return LearningAnswer(status='INSUFFICIENT_EVIDENCE')
        _, row = run_test('learning', answer, {})
        payload = export_json([row])
        for text in ('HIDDEN PROMPT', 'RAW INPUT', 'RAW MODEL RESPONSE'):
            self.assertNotIn(text, payload)
        self.assertEqual(row['model_response_count'], 1)

    def test_repair_stages_recorded(self):
        def answer(**kwargs):
            return call_model('learning', kwargs, [], LearningAnswer, {})
        with patch.object(config, 'MOCK_LLM', False), patch('llm_client._request', side_effect=['invalid', '{"status":"INSUFFICIENT_EVIDENCE"}']):
            _, row = run_test('learning', answer, {'question':'test'})
        self.assertEqual(row['format_retries'], 1)
        self.assertEqual(row['model_response_count'], 2)
        self.assertIn('validation_started', [s['kind'] for s in row['stages']])

    def test_markdown_embedded_fence_is_safe(self):
        _, row = run_test('learning', lambda **k: LearningAnswer(status='INSUFFICIENT_EVIDENCE'), {'question':'``` break'})
        output = export_markdown([row])
        self.assertIn('````json', output)
        self.assertEqual(json.loads(export_json([row]))['runs'][0]['input']['question'], '``` break')
