import json
import unittest
from unittest.mock import patch
import config
from prompts import a_minimal as a, b_structured as b, c_full_system as c
from prompts import templates
from runtime import experiment
from llm_client import call_model
from schemas.outputs import LearningAnswer, NextStepAnswer, DebugAnswer, PracticeQuestion, QuestionExplanation

class HandoffPromptTests(unittest.TestCase):
    def test_all_five_examples_validate(self):
        pairs = [(c.LEARNING, LearningAnswer), (c.NEXT, NextStepAnswer), (c.DEBUG, DebugAnswer),
                 (c.GEN, PracticeQuestion), (c.EXPLAIN, QuestionExplanation)]
        for prompt, schema in pairs:
            with self.subTest(schema=schema.__name__):
                output = prompt[prompt.rfind('\nOUTPUT\n'):]
                obj, _ = json.JSONDecoder().raw_decode(output[output.index('{'):])
                schema.model_validate(obj)
                for evidence in obj.get('evidence', []):
                    self.assertEqual(set(evidence), {'source_id'})

    def test_versioned_prompt_routing(self):
        for task in c.TASKS:
            self.assertEqual(templates.system_prompt(task, 'C'), c.CONTRACT + '\n' + c.TASKS[task])
            self.assertEqual(templates.system_prompt(task, 'B'), b.CONTRACT + '\n' + b.TASKS[task])
            self.assertEqual(templates.system_prompt(task, 'A'), a.CONTRACT + '\n' + a.TASKS[task])

    def test_live_request_uses_handoff_version(self):
        for mode in ('A', 'B', 'C'):
            with patch.object(config, 'MOCK_LLM', True), experiment(mode) as events:
                call_model('learning', {'question':'test'}, [], LearningAnswer, {'status':'INSUFFICIENT_EVIDENCE'})
            request = next(e for e in events if e['kind'] == 'model_request')
            self.assertEqual(request['prompt_version'], {'A': a.VERSION, 'B': b.VERSION, 'C': c.VERSION}[mode])
            self.assertIn('OUTPUT_SCHEMA', request['system'])

    def test_three_prompt_versions_are_distinct(self):
        self.assertEqual([templates.prompt_version(x) for x in ('A', 'B', 'C')],
                         ['A-1.0', 'B-1.0', 'C-1.3'])

    def test_updated_contracts(self):
        self.assertEqual(c.VERSION, 'C-1.3')
        self.assertIn('answer_rationale', c.GEN)
        self.assertIn('STYLE_REFERENCES', c.GEN)
        self.assertNotIn('- Refs:', c.GEN)
        self.assertNotIn('schema has no status', c.EXPLAIN)
        self.assertIn('NEEDS_REVIEW', c.EXPLAIN)
        self.assertIn('INSUFFICIENT_EVIDENCE', c.EXPLAIN)
        self.assertIn('"rationale"', c.DEBUG)
        self.assertIn('`need_more_information`', c.NEXT)
        self.assertIn('universal claim', c.LEARNING)
        self.assertIn('not a confirmed root cause', c.DEBUG)
        self.assertIn('TOPIC ALIGNMENT GATE', c.GEN)
        self.assertIn('application-level human review', c.GEN)

    def test_source_id_in_prose_triggers_one_repair(self):
        invalid = json.dumps({'status':'ANSWERED', 'answer':'RPA follows rules (W1-C-01).',
                              'key_concept':'RPA', 'evidence':[{'source_id':'W1-C-01'}]})
        repaired = json.dumps({'status':'ANSWERED', 'answer':'RPA follows defined rules.',
                               'key_concept':'RPA', 'evidence':[{'source_id':'W1-C-01'}]})
        cards = [{'id':'W1-C-01'}]
        with patch.object(config, 'MOCK_LLM', False), patch('llm_client._request', side_effect=[invalid, repaired]) as request, experiment('C') as events:
            result = call_model('learning', {'question':'What is RPA?'}, cards, LearningAnswer,
                                {'status':'INSUFFICIENT_EVIDENCE'})
        self.assertEqual(request.call_count, 2)
        self.assertNotIn('W1-C-01', result.answer)
        self.assertEqual(sum(e['kind'] == 'format_retry' for e in events), 1)

    def test_unsupported_ai_comparison_triggers_one_repair(self):
        invalid = json.dumps({'status':'ANSWERED',
                              'answer':'AI understands unstructured content and makes judgments.',
                              'key_concept':'RPA vs AI',
                              'evidence':[{'source_id':'W1-C-01'}]})
        repaired = json.dumps({'status':'ANSWERED',
                               'answer':'RPA follows developer-written rules and does not learn or infer on its own.',
                               'key_concept':'RPA vs AI',
                               'evidence':[{'source_id':'W1-C-01'}]})
        cards = [{'id':'W1-C-01',
                  'concept':'RPA performs rule-based repetitive work and is not AI by itself.'}]
        with patch.object(config, 'MOCK_LLM', False), patch('llm_client._request', side_effect=[invalid, repaired]) as request, experiment('C') as events:
            result = call_model('learning', {'question':'Compare RPA and AI.'}, cards,
                                LearningAnswer, {'status':'INSUFFICIENT_EVIDENCE'})
        self.assertEqual(request.call_count, 2)
        self.assertNotIn('unstructured', result.answer)
        self.assertEqual(sum(e['kind'] == 'semantic_retry' for e in events), 1)

    def test_repeated_unsupported_ai_comparison_uses_safe_fallback(self):
        invalid = json.dumps({'status':'ANSWERED',
                              'answer':'AI understands unstructured content and makes judgments.',
                              'key_concept':'RPA vs AI',
                              'evidence':[{'source_id':'W1-C-01'}]})
        cards = [{'id':'W1-C-01',
                  'concept':'RPA performs rule-based repetitive work and is not AI by itself.'}]
        with patch.object(config, 'MOCK_LLM', False), patch('llm_client._request', return_value=invalid) as request, experiment('C') as events:
            result = call_model('learning', {'question':'Compare RPA and AI.'}, cards,
                                LearningAnswer, {'status':'INSUFFICIENT_EVIDENCE'})
        self.assertEqual(request.call_count, 3)
        self.assertNotIn('unstructured', result.answer)
        self.assertEqual(sum(e['kind'] == 'semantic_fallback' for e in events), 1)
