import io
import json
import unittest
from unittest.mock import patch
import config
from llm_client import _request, thinking_options, call_model
from schemas.outputs import LearningAnswer

class ThinkingTests(unittest.TestCase):
    def setUp(self):
        for key, value in [('LLM_BASE_URL', 'https://api.deepseek.com'), ('LLM_MODEL', 'deepseek-v4-flash')]:
            p = patch.object(config, key, value)
            p.start()
            self.addCleanup(p.stop)

    def test_learning_disabled(self):
        self.assertEqual(thinking_options('learning'), {'thinking': {'type': 'disabled'}})

    def test_generation_low(self):
        self.assertEqual(thinking_options('generate'), {'thinking': {'type': 'enabled'}, 'reasoning_effort': 'low'})

    def test_debug_low(self):
        self.assertEqual(thinking_options('debug'), {'thinking': {'type': 'enabled'}, 'reasoning_effort': 'low'})

    def test_other_tasks_unchanged(self):
        for task in ('next_step', 'explain', None):
            self.assertEqual(thinking_options(task), {})

    def test_other_provider_unchanged(self):
        with patch.object(config, 'LLM_BASE_URL', 'https://api.openai.com/v1'):
            self.assertEqual(thinking_options('learning'), {})

    def test_actual_http_payload(self):
        for task in ('learning', 'generate', 'debug'):
            response = io.BytesIO(b'{"choices":[{"message":{"content":"{}"}}]}')
            with patch.object(config, 'LLM_API_KEY', 'test-only'), patch('llm_client.urlopen', return_value=response) as send:
                _request([], task=task)
                payload = json.loads(send.call_args.args[0].data)
                for k, v in thinking_options(task).items():
                    self.assertEqual(payload[k], v)

    def test_task_preserved_on_repair(self):
        with patch.object(config, 'MOCK_LLM', False), patch('llm_client._request', side_effect=['bad', '{"status":"INSUFFICIENT_EVIDENCE"}']) as send:
            call_model('learning', {}, [], LearningAnswer, {})
            self.assertEqual([c.kwargs['task'] for c in send.call_args_list], ['learning', 'learning'])
