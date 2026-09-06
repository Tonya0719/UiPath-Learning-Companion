import streamlit as st
from html import escape

import config
from modules.learning_explainer import answer_concept_question
from modules.guided_practice import get_next_step, debug_workflow
from modules.assessment_coach import generate_question, explain_question
from modules.common import evidence_for
from retrieval.retriever import load, by_ids, exercise_catalog
import ui_examples
from ui_locale import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    MODE_LABELS,
    STATUS_LABELS,
    DIAGNOSIS_LABELS,
    TASK_LABELS,
    STAGE_LABELS,
    tr,
)
from ui_theme import apply_theme, render_footer
from ui_runs import run_test, export_json, export_markdown


def current_language():
    lang = st.session_state.get('ui_language', config.UI_LANGUAGE or DEFAULT_LANGUAGE)
    return lang if lang in LANGUAGE_LABELS else DEFAULT_LANGUAGE


def set_language(language):
    st.session_state.ui_language = language


ACTIVE_MODULE_KEY = 'ui_active_module'

MODULE_STATE_KEYS = {
    'learning': ['learn_question', 'learn_week', 'learn_depth', 'learning'],
    'practice': ['build_week', 'help_mode', 'build_result', 'next_last', 'next_state',
                 'debug_activity', 'debug_error', 'debug_change'],
    'generate': ['gen_topic', 'gen_difficulty', 'gen_type', 'question', 'assessment_result',
                 'example_question'],
}

GLOBAL_STATE_KEYS = {'ui_language', 'ui_language_picker', ACTIVE_MODULE_KEY}


def set_active_module(module):
    st.session_state[ACTIVE_MODULE_KEY] = module


def infer_active_module():
    scores = {}
    for module, keys in MODULE_STATE_KEYS.items():
        score = sum(1 for key in keys if st.session_state.get(key) not in (None, '', [], {}))
        scores[module] = score
    best = max(scores.values(), default=0)
    if best > 0:
        tied = [module for module, score in scores.items() if score == best]
        stored = st.session_state.get(ACTIVE_MODULE_KEY)
        if stored in tied:
            return stored
        for module in ('learning', 'practice', 'generate'):
            if module in tied:
                return module
    return st.session_state.get(ACTIVE_MODULE_KEY, 'learning')


def clear_module_state(module):
    keep = set(GLOBAL_STATE_KEYS)
    for key in list(st.session_state.keys()):
        if key in keep:
            continue
        if key.startswith('choice_'):
            st.session_state.pop(key, None)
            continue
        if key.startswith('exercise_'):
            st.session_state.pop(key, None)
            continue
        if any(key in keys for keys in MODULE_STATE_KEYS.values()):
            st.session_state.pop(key, None)
            continue
        if key in {'test_runs', 'export_selection'}:
            st.session_state.pop(key, None)


def handle_language_change():
    active_module = infer_active_module()
    st.session_state.ui_language = st.session_state.ui_language_picker
    st.session_state[ACTIVE_MODULE_KEY] = active_module
    clear_module_state(active_module)


def mode_options(language):
    return [MODE_LABELS[language]['next_step'], MODE_LABELS[language]['debug']]


def mode_key(language, value):
    return value == MODE_LABELS[language]['debug']


st.set_page_config(page_title='PE6202 UiPath Learning Companion', layout='wide')
apply_theme()

if 'ui_language' not in st.session_state:
    set_language(config.UI_LANGUAGE if config.UI_LANGUAGE in LANGUAGE_LABELS else DEFAULT_LANGUAGE)

lang = current_language()

st.title(tr(lang, 'title'))
st.caption(tr(lang, 'caption'))
with st.sidebar:
    chosen_language = st.radio(
        '界面语言' if lang == 'zh' else 'Interface language',
        options=list(LANGUAGE_LABELS),
        format_func=lambda code: LANGUAGE_LABELS[code],
        index=list(LANGUAGE_LABELS).index(lang),
        key='ui_language_picker',
        on_change=handle_language_change,
    )

lang = current_language()

if config.MOCK_LLM:
    st.warning(tr(lang, 'mock_warning'))
else:
    st.info(tr(lang, 'real_model_info', model=config.LLM_MODEL))


def attempt(task, function, **inputs):
    with st.status(tr(lang, 'checking_input'), expanded=False) as indicator:
        def progress(event):
            label = STAGE_LABELS[lang].get(event['kind'])
            if label:
                if event['kind'] == 'model_request' and event.get('mock'):
                    label = tr(lang, 'demo_mode_ready')
                indicator.update(label=label + '…')

        result, row = run_test(task, function, inputs, progress, language=lang)
        label = tr(lang, 'request_failed') if row['error'] else tr(lang, 'processing_complete')
        indicator.update(
            label=f"{label} · {tr(lang, 'elapsed', seconds=row['elapsed_seconds'])}",
            state='error' if row['error'] else 'complete',
            expanded=False,
        )
    history = st.session_state.setdefault('test_runs', [])
    history.append(row)
    st.session_state.test_runs = history[-50:]
    if row['error']:
        st.error(row['error']['message'])
    return result


def fill_example(name):
    if name == 'learning':
        set_active_module('learning')
    elif name in {'next_step', 'debug'}:
        set_active_module('practice')
    else:
        set_active_module('generate')
    examples = ui_examples.examples(lang)
    if name == 'explain':
        q = ui_examples.explanation_example(lang)
        st.session_state.question = q
        st.session_state['choice_' + q.question_id] = 'B'
        st.session_state.example_question = True
        st.session_state.pop('assessment_result', None)
        return
    values = dict(examples[name])
    if name in {'next_step', 'debug'}:
        values['help_mode'] = MODE_LABELS[lang][name]
    st.session_state.update(values)
    if name == 'learning':
        st.session_state.pop('learning', None)
    elif name in {'next_step', 'debug'}:
        st.session_state.pop('build_result', None)
    else:
        st.session_state.pop('question', None)
        st.session_state.pop('assessment_result', None)
        st.session_state.example_question = False


def sources(evidence):
    with st.expander(tr(lang, 'sources'), expanded=False):
        if not evidence:
            st.caption(tr(lang, 'no_evidence'))
        for e in evidence:
            st.write(f'{e.source_label} [{e.source_id}]')
            if e.source_pages:
                st.caption(tr(lang, 'pages') + ', '.join(map(str, e.source_pages)))
            if e.url:
                st.link_button(tr(lang, 'official_sources'), e.url)
            if e.product:
                checked_label = 'Checked on' if lang == 'en' else '核对日期'
                st.caption(
                    f"{e.product} · {e.version or tr(lang, 'source_missing_version')} · "
                    f"{checked_label}: {e.checked_on or tr(lang, 'source_missing_date')}"
                )
            st.write(e.text)


def status(result):
    labels = STATUS_LABELS[lang]
    render = st.success if result.status in {'ANSWERED', 'GENERATED'} else st.warning
    render(labels.get(result.status, result.status))
    for item in getattr(result, 'need_more_information', []):
        st.write(f"{tr(lang, 'need_more_information')}: {item}")
    if getattr(result, 'reason', ''):
        st.write(result.reason)


try:
    catalog = exercise_catalog()
    counts = {t: len(load([t])) for t in ('concept', 'task', 'question', 'official')}
except (ValueError, OSError):
    st.error(tr(lang, 'request_failed') + '：' + ('Please run the data validation script first.' if lang == 'en' else '请先运行数据检查脚本。'))
    st.stop()


with st.sidebar:
    st.header(tr(lang, 'knowledge_bank_status'))
    st.write(tr(lang, 'counts', concept=counts['concept'], task=counts['task'], question=counts['question'], official=counts['official']))
    st.caption(tr(lang, 'review_note'))


active_module = st.radio(
    'Module',
    ['learning', 'practice', 'generate'],
    key=ACTIVE_MODULE_KEY,
    format_func=lambda value: {
        'learning': tr(lang, 'tab_learning'),
        'practice': tr(lang, 'tab_next'),
        'generate': tr(lang, 'tab_generate'),
    }[value],
    horizontal=True,
    label_visibility='collapsed',
)

if active_module == 'learning':
    st.button(tr(lang, 'fill_learning'), on_click=fill_example, args=('learning',))
    with st.form('learning_form'):
        question = st.text_area(tr(lang, 'question_label'), placeholder=tr(lang, 'question_placeholder'), max_chars=12000, key='learn_question')
        week_options = [tr(lang, 'week_any'), 1, 2, 3, 4, 5]
        week = st.selectbox(tr(lang, 'week_label'), week_options, key='learn_week')
        depth = st.selectbox(tr(lang, 'depth_label'), ['Brief', 'Detailed'], key='learn_depth')
        ask = st.form_submit_button(tr(lang, 'ask_button'))
    if ask:
        submitted_question = st.session_state.get('learn_question', question)
        st.session_state.learning = attempt(
            'learning',
            answer_concept_question,
            question=submitted_question,
            week=None if week == tr(lang, 'week_any') else week,
            depth=depth,
        )
    r = st.session_state.get('learning')
    if r:
        status(r)
        st.write(r.answer)
        if r.key_concept:
            st.caption(f"{tr(lang, 'key_concept')} {r.key_concept}")
        if r.exercise_connection:
            st.write(f"{tr(lang, 'exercise_connection')} {r.exercise_connection}")
        if r.common_misunderstanding:
            st.write(f"{tr(lang, 'common_misunderstanding')} {r.common_misunderstanding}")
        sources(r.evidence)

if active_module == 'practice':
    sample_next, sample_debug = st.columns(2)
    sample_next.button(tr(lang, 'fill_next'), on_click=fill_example, args=('next_step',))
    sample_debug.button(tr(lang, 'fill_debug'), on_click=fill_example, args=('debug',))
    w = st.selectbox(tr(lang, 'week_select'), list(catalog), key='build_week')
    ex = st.selectbox(tr(lang, 'exercise_select'), catalog[w], key=f'exercise_{w}')
    modes = mode_options(lang)
    selected_mode = st.radio(tr(lang, 'mode_label'), modes, horizontal=True, key='help_mode')
    with st.form('practice_form'):
        if selected_mode == MODE_LABELS[lang]['next_step']:
            last = st.text_input(tr(lang, 'last_step'), max_chars=12000, key='next_last')
            state = st.text_area(tr(lang, 'current_state'), max_chars=12000, key='next_state')
        else:
            activity = st.text_input(tr(lang, 'activity_name'), max_chars=1000, key='debug_activity')
            error = st.text_area(tr(lang, 'error_message'), max_chars=12000, key='debug_error')
            change = st.text_input(tr(lang, 'recent_change'), max_chars=4000, key='debug_change')
        build = st.form_submit_button(tr(lang, 'get_guidance'))
    context = (w, ex, selected_mode)
    if build:
        r = (
            attempt('next_step', get_next_step, week=w, exercise=ex, last_completed_step=last, current_state=state)
            if selected_mode == MODE_LABELS[lang]['next_step']
            else attempt('debug', debug_workflow, week=w, exercise=ex, activity=activity, error_message=error, recent_change=change)
        )
        st.session_state.build_result = (context, r)
    stored = st.session_state.get('build_result')
    if stored and stored[0] == context and stored[1]:
        r = stored[1]
        status(r)
        if selected_mode == MODE_LABELS[lang]['next_step']:
            st.write(r.where_you_are)
            for i, action in enumerate(r.next_actions, 1):
                st.write(f'{i}. {action}')
            if r.activity_or_expression:
                st.code('\n'.join(r.activity_or_expression), language=None)
            if r.expected_result:
                st.write(f"{tr(lang, 'expected_result')} {r.expected_result}")
            if r.common_mistake:
                st.write(f"{tr(lang, 'mistake')} {r.common_mistake}")
        else:
            categories = DIAGNOSIS_LABELS[lang]
            st.caption(tr(lang, 'question_type') + categories.get(r.diagnosis_type, r.diagnosis_type))
            if r.possible_causes:
                st.caption(
                    'The following are hypotheses to verify, not confirmed root causes. Check the first one before expanding others.'
                    if lang == 'en'
                    else '以下是待验证的排查方向，并非已确认的根因。先检查第一项，未解决再展开其他原因。'
                )
                first = r.possible_causes[0]
                with st.container(border=True):
                    st.markdown(f"### 01 · {tr(lang, 'priority_check')}")
                    st.write(first.cause)
                    st.markdown(f"**{tr(lang, 'check')}**")
                    st.write(first.check)
                    st.markdown(f"**{tr(lang, 'fix')}**")
                    st.write(first.fix)
                    if first.rationale:
                        with st.expander(tr(lang, 'why_first')):
                            st.write(first.rationale)
                if len(r.possible_causes) > 1:
                    st.markdown(f"#### {tr(lang, 'other_causes')}")
                    for i, c in enumerate(r.possible_causes[1:], 2):
                        with st.expander(f"{i}. {tr(lang, 'priority_check')}"):
                            st.write(c.cause)
                            st.markdown(f"**{tr(lang, 'check')}**")
                            st.write(c.check)
                            st.markdown(f"**{tr(lang, 'fix')}**")
                            st.write(c.fix)
                            if c.rationale:
                                st.markdown(f"**{tr(lang, 'why_first')}**")
                                st.write(c.rationale)
        if r.verification:
            with st.container(border=True):
                st.markdown(
                    f"#### {tr(lang, 'verification_after_fix')}" if selected_mode == MODE_LABELS[lang]['debug']
                    else f"#### {tr(lang, 'verification_complete')}"
                )
                st.write(r.verification)
        sources(r.evidence)

if active_module == 'generate':
    st.caption(
        'The generated item is for learning practice, not exam prediction. Questions and explanations still need to be checked against the source material.'
        if lang == 'en'
        else '生成的是学习练习，不是考试预测。题目与解析仍需结合原资料核对。'
    )
    sample_gen, sample_explain = st.columns(2)
    sample_gen.button(tr(lang, 'fill_generate'), on_click=fill_example, args=('generate',))
    sample_explain.button(tr(lang, 'fill_explain'), on_click=fill_example, args=('explain',))
    st.caption(tr(lang, 'sample_caption'))
    with st.form('generate_form'):
        topic = st.text_input(tr(lang, 'topic_label'), placeholder=tr(lang, 'topic_placeholder'), max_chars=1000, key='gen_topic')
        diff = st.selectbox(tr(lang, 'difficulty_label'), ['Easy', 'Medium', 'Hard'], index=1, key='gen_difficulty')
        qt = st.selectbox(tr(lang, 'question_type_label'), ['Concept Distinction', 'Workflow Logic', 'Activity Selection', 'Error Diagnosis', 'Activity Placement', 'Output Prediction'], key='gen_type')
        generate = st.form_submit_button(tr(lang, 'generate_button'))
    if generate:
        st.session_state.question = attempt('generate', generate_question, topic=topic, difficulty=diff, question_type=qt)
        st.session_state.example_question = False
        st.session_state.pop('assessment_result', None)
    q = st.session_state.get('question')
    if q:
        status(q)
        if q.status == 'GENERATED':
            if not st.session_state.get('example_question') and q.review_status == 'NEEDS_HUMAN_REVIEW':
                st.warning(tr(lang, 'review_pending'))
            if st.session_state.get('example_question'):
                st.caption(tr(lang, 'review_example'))
            with st.container(key='practice_question_card'):
                with st.form('answer_' + q.question_id, border=False):
                    st.markdown(
                        '<div class="question-eyebrow">' + tr(lang, 'question_stem') + '</div>'
                        '<div class="question-stem">'
                        + escape(q.question) + '</div>',
                        unsafe_allow_html=True,
                    )
                    answer = st.radio(tr(lang, 'select_answer'), list(q.options), index=None, format_func=lambda k: f'{k}. {q.options[k]}', key='choice_' + q.question_id)
                    submit = st.form_submit_button(tr(lang, 'submit_answer'))
            if submit:
                if answer is None:
                    st.warning(tr(lang, 'need_choose'))
                else:
                    explanation = attempt('explain', explain_question, question=q, user_answer=answer)
                    st.session_state.assessment_result = (q.question_id, answer, explanation)
            saved = st.session_state.get('assessment_result')
            if saved and saved[0] == q.question_id and saved[2]:
                _, submitted_answer, exp = saved
                st.markdown('### ' + tr(lang, 'answer_analysis'))
                st.caption(tr(lang, 'last_answer') + submitted_answer)
                status(exp)
                if exp.status == 'ANSWERED':
                    if submitted_answer == exp.correct_answer:
                        st.success(tr(lang, 'correct'))
                    else:
                        st.info(tr(lang, 'correct_answer') + exp.correct_answer)
                    st.write(exp.why_correct)
                    for k, value in exp.why_others_wrong.items():
                        st.write(f'{k}: {value}')
                    st.write(f"{tr(lang, 'learning_point')} {exp.learning_takeaway}")
                    if exp.student_misunderstanding:
                        st.write(f"{tr(lang, 'reusable_point')} {exp.student_misunderstanding}")
                sources(exp.evidence)
                sources([evidence_for(c) for c in by_ids(q.course_evidence_ids)])

st.divider()
with st.expander(tr(lang, 'log_section'), expanded=False):
    st.caption(tr(lang, 'log_caption'))
    st.caption(tr(lang, 'log_redaction'))
    rows = st.session_state.get('test_runs', [])
    if not rows:
        st.info(tr(lang, 'no_runs'))
    else:
        st.dataframe([
            {
                tr(lang, 'record'): r['run_id'],
                tr(lang, 'task'): r['task_label'],
                tr(lang, 'version'): r['prompt_version'],
                tr(lang, 'mode'): tr(lang, 'display_mode_mock') if r['mock'] else tr(lang, 'display_mode_real'),
                tr(lang, 'status'): 'ERROR' if r['error'] else r['output'].get('status', ''),
                tr(lang, 'elapsed_s'): r['elapsed_seconds'],
            }
            for r in rows
        ], hide_index=True)
        selected_id = st.selectbox(tr(lang, 'view_record'), [r['run_id'] for r in reversed(rows)], key='export_selection')
        selected = next(r for r in rows if r['run_id'] == selected_id)
        st.caption(
            f"{selected['task_label']} · {selected['prompt_version']} · {tr(lang, 'elapsed', seconds=selected['elapsed_seconds'])}"
        )
        st.text(tr(lang, 'stage_label') + ' → '.join(s['label'] for s in selected['stages']))
        st.json(selected, expanded=False)
        download_one, download_all = st.columns(2)
        download_one.download_button(
            tr(lang, 'download_one'),
            export_json([selected], language=lang),
            file_name=f"C_test_{selected_id}.json",
            mime='application/json',
            on_click='ignore',
        )
        download_all.download_button(
            tr(lang, 'download_all'),
            export_json(rows, language=lang),
            file_name='C_function_tests.json',
            mime='application/json',
            on_click='ignore',
        )
        st.download_button(
            tr(lang, 'download_md'),
            export_markdown(rows, language=lang),
            file_name='C_function_tests.md',
            mime='text/markdown',
            on_click='ignore',
        )

render_footer()
