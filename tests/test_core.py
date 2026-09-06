import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from pydantic import ValidationError
import config
import llm_client
from runtime import experiment
from retrieval.retriever import load, retrieve, task_context, exercise_catalog
from modules.learning_explainer import answer_concept_question
from modules.guided_practice import get_next_step, debug_workflow
from modules.assessment_coach import generate_question, explain_question
from modules.common import evidence_for, ground
from schemas.outputs import LearningAnswer, PracticeQuestion, QuestionExplanation
from evaluation.run_eval import check_cases, FUNCTIONS
from scripts.validate_data import validate

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.mock = patch.object(config, 'MOCK_LLM', True)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_full_data_counts(self):
        self.assertEqual([len(load([k])) for k in ('concept', 'task', 'question', 'official')], [31,20,9,3])

    def test_data_validation(self):
        self.assertEqual(validate()['errors'], [])

    def test_answers_still_unverified(self):
        self.assertTrue(all(not q['answer_verified'] for q in load(['question'])))

    def test_unknown_week_does_not_fallback(self):
        self.assertEqual(retrieve('invoice', ['task'], week=99), [])

    def test_wrong_exercise_does_not_fallback(self):
        self.assertEqual(retrieve('invoice', ['task'], week=1, exercise='Document Data Extraction'), [])

    def test_unknown_topic_does_not_fallback(self):
        self.assertEqual(retrieve('invoice', ['concept'], topic='quantumzzzz'), [])

    def test_zero_score_not_returned(self):
        self.assertEqual(retrieve('zzzxqv999', ['concept', 'task']), [])

    def test_chinese_anchor_query(self):
        self.assertIn('W1-C-04', [c['id'] for c in retrieve('锚点选择器', ['concept'], week=1)])

    def test_procedure_is_searchable(self):
        cards = retrieve('Indicate Target', ['task'], week=1)
        self.assertIn('W1-T-02', [c['id'] for c in cards])

    def test_task_evidence_exposes_goal_and_procedure(self):
        card = next(c for c in load(['task']) if c['id'] == 'W3-T-04')
        evidence = evidence_for(card)
        self.assertIn('Goal:', evidence.text)
        self.assertIn('Read Range', evidence.text)
        self.assertIn('Has Header=False', evidence.text)
        self.assertIn('How to write to Append', evidence.text)
        self.assertIn('Delete Range', evidence.text)

    def test_sequence_context(self):
        ids = [c['id'] for c in task_context('Type Into username', 1, 'User Interface Automation')]
        self.assertIn('W1-T-01', ids)
        self.assertIn('W1-T-03', ids)
        self.assertTrue(all(i.startswith('W1-') for i in ids))

    def test_catalog(self):
        self.assertEqual(set(exercise_catalog()), {1,2,3,4})

    def test_blank_learning(self):
        self.assertEqual(answer_concept_question(' ').status, 'NEED_MORE_INFORMATION')

    def test_learning_scope(self):
        self.assertEqual(answer_concept_question('RPA', week=9).status, 'OUT_OF_SCOPE')

    def test_learning_scope_reply_follows_english(self):
        r = answer_concept_question('Explain the Week 9 lecture.', week=9)
        self.assertEqual(r.answer, 'The current scope supports Weeks 1–5.')

    def test_learning_no_evidence(self):
        self.assertEqual(answer_concept_question('zzzxqv999').status, 'INSUFFICIENT_EVIDENCE')

    def test_demo_not_canned_index_reply(self):
        r = answer_concept_question('RPA', week=1)
        self.assertNotIn('CurrentRowNumber', r.answer)
        self.assertIn('Evidence preview', r.answer)
        self.assertTrue(r.evidence[0].source_pages)

    def test_next_missing_context(self):
        r = get_next_step(1, 'User Interface Automation', '', '')
        self.assertEqual(r.status, 'NEED_MORE_INFORMATION')
        self.assertTrue(r.need_more_information[0].startswith('Please'))

    def test_debug_missing_info(self):
        r = debug_workflow(3, 'Document Data Extraction', '', 'wrong result')
        self.assertEqual(r.status, 'NEED_MORE_INFORMATION')

    def test_demo_no_fake_diagnosis(self):
        r = debug_workflow(3, 'Document Data Extraction', 'Write Range', 'Only final invoice remains')
        self.assertEqual(r.possible_causes, [])
        self.assertTrue(r.evidence)

    def test_empty_unsupported_question_validates(self):
        q = PracticeQuestion(status='UNSUPPORTED_TOPIC')
        self.assertEqual(q.options, {})
        self.assertEqual(q.review_status, 'NOT_APPLICABLE')

    def test_unsupported_topic_keeps_requested_fields_and_language(self):
        q = generate_question('Quantum chromodynamics scattering amplitudes', 'Hard', 'Output Prediction')
        self.assertEqual(q.status, 'UNSUPPORTED_TOPIC')
        self.assertEqual(q.difficulty, 'Hard')
        self.assertEqual(q.question_type, 'Output Prediction')
        self.assertTrue(q.reason.startswith('No course evidence'))

    def test_datatable_writeback_topic_ranks_direct_concept_first(self):
        cards = retrieve('DataTable write-back', ['concept', 'task'], topic='DataTable write-back')
        self.assertEqual(cards[0]['id'], 'W2-C-01')

    def test_generator_sends_only_direct_topic_evidence(self):
        with experiment('C') as events:
            generate_question('DataTable write-back', 'Medium', 'Workflow Logic')
        request = next(e for e in events if e['kind'] == 'model_request')
        evidence = json.loads(request['user'])['EVIDENCE']
        self.assertEqual([c['id'] for c in evidence], ['W2-C-01'])
        routing = next(e for e in events if e['kind'] == 'direct_topic_evidence')
        self.assertEqual(routing['direct_ids'], ['W2-C-01'])

    def test_generated_question_requires_human_review(self):
        q = PracticeQuestion(status='GENERATED', question='Test question?',
                             options={'A':'one','B':'two','C':'three','D':'four'},
                             correct_answer='A', answer_rationale='Supported by evidence')
        self.assertEqual(q.review_status, 'NEEDS_HUMAN_REVIEW')

    def test_generated_invalid_options_rejected(self):
        with self.assertRaises(ValidationError):
            PracticeQuestion(status='GENERATED', question='test', options={'A':'one'}, correct_answer='Z')

    def test_unknown_citation_rejected(self):
        r = LearningAnswer(status='ANSWERED', answer='unsafe claim', evidence=[{'source_id':'FAKE'}])
        r = ground(r, load(['concept']))
        self.assertEqual(r.status, 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(r.answer, '')

    def test_citation_metadata_rebuilt(self):
        r = LearningAnswer(status='ANSWERED', answer='RPA', evidence=[{'source_id':'W1-C-01','source_pages':[999],'source_label':'fake'}])
        r = ground(r, load(['concept']))
        self.assertEqual(r.evidence[0].source_pages, [4,5])
        self.assertNotEqual(r.evidence[0].source_label, 'fake')

    def test_twenty_draft_cases(self):
        cases = json.loads((config.ROOT / 'evaluation/cases.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases), 20)
        self.assertTrue(all(c['review_status'] == 'draft' for c in cases))
        self.assertEqual(check_cases(cases), [])
        self.assertEqual({m:sum(c['module']==m for c in cases) for m in FUNCTIONS}, {'learning':7,'next_step':3,'debug':4,'generate':3,'explain':3})

    def test_twenty_approved_final_cases(self):
        cases = json.loads((config.ROOT / 'evaluation/final_cases.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases), 20)
        self.assertTrue(all(c['review_status'] == 'approved' for c in cases))
        self.assertTrue(all(c['used_for_development'] is False for c in cases))
        self.assertEqual(check_cases(cases), [])
        self.assertEqual({m:sum(c['module']==m for c in cases) for m in FUNCTIONS},
                         {'learning':7,'next_step':3,'debug':4,'generate':3,'explain':3})
        development_ids = {c['case_id'] for c in json.loads(
            (config.ROOT / 'evaluation/cases.json').read_text(encoding='utf-8'))}
        self.assertTrue(development_ids.isdisjoint(c['case_id'] for c in cases))

    def test_all_draft_cases_smoke(self):
        for c in json.loads((config.ROOT / 'evaluation/cases.json').read_text(encoding='utf-8')):
            with self.subTest(case=c['case_id']):
                self.assertTrue(FUNCTIONS[c['module']](**c['input']).status)

    def test_baseline_has_no_retrieval(self):
        for mode in ('A','B'):
            with experiment(mode):
                self.assertEqual(retrieve('RPA'), [])
        self.assertTrue(retrieve('RPA'))

    def test_schema_sent_and_baseline_separation(self):
        for mode in ('A','B','C'):
            with experiment(mode) as events:
                answer_concept_question('RPA', week=1)
            request = next(e for e in events if e['kind'] == 'model_request')
            self.assertIn('OUTPUT_SCHEMA', request['system'])
            self.assertEqual('EVIDENCE' in json.loads(request['user']), mode == 'C')

    def test_unverified_answers_not_in_style_prompt(self):
        with experiment('C') as events:
            generate_question('anchor')
        refs = json.loads(next(e for e in events if e['kind'] == 'model_request')['user'])['STYLE_REFERENCES']
        self.assertTrue(refs)
        self.assertTrue(all('correct_answer' not in r and 'answer_rationale' not in r for r in refs))

    def question_fixture(self):
        cases = json.loads((config.ROOT / 'evaluation/cases.json').read_text(encoding='utf-8'))
        return PracticeQuestion.model_validate(next(c for c in cases if c['case_id']=='M3_04')['input']['question'])

    def test_explanation_preserves_evidence(self):
        with experiment('C') as events:
            explain_question(self.question_fixture(), 'A')
        evidence = json.loads(next(e for e in events if e['kind'] == 'model_request')['user'])['EVIDENCE']
        self.assertEqual([c['id'] for c in evidence], ['W2-C-01'])

    def test_inconsistent_explanation_not_graded(self):
        bad = QuestionExplanation(status='ANSWERED', correct_answer='B', why_correct='wrong', why_others_wrong={'A':'wrong','C':'wrong','D':'wrong'})
        with patch('modules.assessment_coach.call_model', return_value=bad):
            self.assertEqual(explain_question(self.question_fixture(), 'A').status, 'NEEDS_REVIEW')

    def test_repeated_teacher_question_rejected(self):
        ref = load(['question'])[0]
        q = PracticeQuestion(status='GENERATED', question=ref['question'], options=ref['options'], correct_answer=ref['correct_answer'], answer_rationale='test', course_evidence_ids=['W1-C-04'])
        with patch('modules.assessment_coach.call_model', return_value=q):
            self.assertEqual(generate_question('anchor').status, 'NEEDS_REVIEW')

    def test_missing_api_key_has_safe_error(self):
        with patch.object(config, 'LLM_API_KEY', ''):
            with self.assertRaises(llm_client.ModelError):
                llm_client._request([])

    def test_transport_error_safe(self):
        with patch.object(config, 'LLM_API_KEY', 'test-not-real'), patch('llm_client.urlopen', side_effect=URLError('SECRET')):
            with self.assertRaises(llm_client.ModelError) as exc:
                llm_client._request([])
            self.assertNotIn('SECRET', str(exc.exception))

    def test_invalid_model_json_one_repair(self):
        with patch.object(config, 'MOCK_LLM', False), patch('llm_client._request', side_effect=['bad', '{"status":"INSUFFICIENT_EVIDENCE"}']) as request:
            r = llm_client.call_model('learning', {}, [], LearningAnswer, {})
            self.assertEqual(r.status, 'INSUFFICIENT_EVIDENCE')
            self.assertEqual(request.call_count, 2)

    def test_repeated_invalid_model_json_raises(self):
        with patch.object(config, 'MOCK_LLM', False), patch('llm_client._request', return_value='bad') as request:
            with self.assertRaises(llm_client.ModelError):
                llm_client.call_model('learning', {}, [], LearningAnswer, {})
            self.assertEqual(request.call_count, 2)

if __name__ == '__main__':
    unittest.main()
