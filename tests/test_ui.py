import importlib.util
import unittest
from unittest.mock import patch
import config
from schemas.outputs import PracticeQuestion, QuestionExplanation, DebugAnswer

@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit is not installed')
class UITests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.mock = patch.object(config, 'MOCK_LLM', True)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.app = AppTest.from_file(str(config.ROOT / 'app.py'), default_timeout=20).run()

    def button(self, label):
        return next(b for b in self.app.button if b.label == label)

    def test_initial_three_tabs_and_counts(self):
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.tabs), 3)
        self.assertTrue(any('9' in x.value and '例题' in x.value for x in self.app.markdown))

    def test_theme_and_group_footer(self):
        from ui_theme import MEMBERS
        markup = '\n'.join(x.value for x in self.app.markdown)
        self.assertIn('#181C62', markup)
        self.assertIn('#D71440', markup)
        self.assertNotIn('color-scheme:light', markup)
        self.assertNotIn('background:white', markup)
        self.assertIn('currentColor', markup)
        footer = next(x.value for x in self.app.markdown if '<footer ' in x.value)
        self.assertIn('PE6203 A1 · Group 5', footer)
        self.assertIn('© 2026 Group 5', footer)
        for name in MEMBERS:
            self.assertIn(name, footer)

    def test_learning_request_and_sources(self):
        self.app.text_area[0].set_value('RPA 是什么？')
        self.button('提问').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('资料预览' in x.value for x in self.app.markdown))
        self.assertTrue(any('页码' in x.value for x in self.app.caption))

    def test_next_step_missing_information_visible(self):
        self.button('获取指导').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('需要补充信息' in x.value for x in self.app.warning))

    def test_debug_mode_renders(self):
        self.app.radio[0].set_value('Debug').run()
        self.button('获取指导').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('需要补充信息' in x.value for x in self.app.warning))

    def test_generate_empty_topic(self):
        self.button('生成题目').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('知识点' in x.value for x in self.app.warning))

    def test_fill_learning_no_api_call(self):
        with patch('llm_client._request', side_effect=AssertionError('No API calls while filling examples')):
            self.button('填入知识问答示例').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.selectbox(key='learn_week').value, 2)
        self.assertIn('DataTable', self.app.text_area(key='learn_question').value)
        self.assertNotIn('test_runs', self.app.session_state)

    def test_switch_debug_and_next_examples(self):
        self.button('填入 Debug 示例').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.selectbox(key='build_week').value, 3)
        self.assertEqual(self.app.radio(key='help_mode').value, 'Debug')
        self.assertEqual(self.app.text_input(key='debug_activity').value, 'Write Range')
        self.button('填入下一步示例').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.selectbox(key='build_week').value, 1)
        self.assertEqual(self.app.radio(key='help_mode').value, '下一步')
        self.assertIn('Use Application', self.app.text_input(key='next_last').value)

    def test_fill_generation_example(self):
        self.button('填入出题示例').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.selectbox(key='gen_type').value, 'Workflow Logic')
        self.assertIn('DataTable', self.app.text_input(key='gen_topic').value)
        self.assertNotIn('test_runs', self.app.session_state)

    def test_explanation_example_no_generation_required(self):
        with patch('llm_client._request', side_effect=AssertionError('No API calls on load')):
            self.button('载入讲题示例').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.radio(key='choice_EXAMPLE-DATATABLE').value, 'B')
        self.assertNotIn('test_runs', self.app.session_state)
        self.button('提交答案').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state['test_runs'][-1]['task'], 'explain')
        self.assertEqual(self.app.session_state['test_runs'][-1]['input']['user_answer'], 'B')

    def test_export_history_persists_without_resubmission(self):
        self.button('填入知识问答示例').click().run()
        self.button('提问').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.session_state['test_runs']), 1)
        self.assertTrue(any('测试与导出' in e.label for e in self.app.expander))
        self.assertTrue(any('总耗时' in s.label for s in self.app.status))
        self.assertEqual(len(self.app.get('download_button')), 3)
        self.app.run()
        self.assertEqual(len(self.app.session_state['test_runs']), 1)

    def test_debug_visual_hierarchy(self):
        response = DebugAnswer(status='ANSWERED', diagnosis_type='WORKFLOW_LOGIC',
            possible_causes=[{'cause':f'候选原因{i}', 'check':f'检查{i}', 'fix':f'修复{i}', 'rationale':f'依据{i}'} for i in range(1,4)],
            verification='用两张 PDF 检查是否全部保留。')
        self.app.radio[0].set_value('Debug').run()
        with patch('modules.guided_practice.debug_workflow', return_value=response):
            self.button('获取指导').click().run()
        self.assertFalse(self.app.exception)
        content = '\n'.join(x.value for x in self.app.markdown)
        for title in ('优先检查', '其他可能原因', '修复后验证'):
            self.assertIn(title, content)
        self.assertEqual(len([e for e in self.app.expander if '排查方向' in e.label]), 2)
        self.assertTrue(any('为什么先检查' in e.label for e in self.app.expander))

    def test_answer_hidden_then_submission_stable(self):
        question = PracticeQuestion(status='GENERATED', question_id='UI-TEST', question='Which action writes the edit back?',
            options={'A':'Write back', 'B':'Wait', 'C':'Rename', 'D':'Restart'}, correct_answer='A', answer_rationale='Write explicitly',
            course_evidence_ids=['W2-C-01'], knowledge_point='DataTable')
        explanation = QuestionExplanation(status='ANSWERED', correct_answer='A', why_correct='Explicit write-back is required.',
            why_others_wrong={'B':'No automatic sync', 'C':'Not a write', 'D':'Not a write'}, learning_takeaway='Write back explicitly.')
        with patch('modules.assessment_coach.generate_question', return_value=question), patch('modules.assessment_coach.explain_question', return_value=explanation):
            self.button('生成题目').click().run()
            self.assertFalse(self.app.exception)
            self.assertFalse(any('Explicit write-back' in x.value for x in self.app.markdown))
            self.app.radio[1].set_value('A')
            self.button('提交答案').click().run()
            self.assertFalse(self.app.exception)
            self.assertTrue(any('回答正确' in x.value for x in self.app.success))
            self.app.radio[1].set_value('B').run()
            self.assertTrue(any('上次提交的答案：A' in x.value for x in self.app.caption))
            self.assertTrue(any('回答正确' in x.value for x in self.app.success))

if __name__ == '__main__':
    unittest.main()
