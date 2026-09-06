import streamlit as st
from html import escape
import config
from modules.learning_explainer import answer_concept_question
from modules.guided_practice import get_next_step, debug_workflow
from modules.assessment_coach import generate_question, explain_question
from modules.common import evidence_for
from retrieval.retriever import load, by_ids, exercise_catalog
import ui_examples
from ui_theme import apply_theme, render_footer
from ui_runs import run_test, export_json, export_markdown, STAGES

st.set_page_config(page_title='PE6202 UiPath Learning Companion', layout='wide')
apply_theme()
st.title('PE6202 UiPath Learning Companion')
st.caption('知识理解 · 操作实践 · 测验巩固｜Weeks 1–5 知识 / Weeks 1–4 练习')
if config.MOCK_LLM:
    st.warning('当前是资料预览模式：不会调用模型，也不生成真实诊断或试题。配置 .env 后重启可进行真实模型测试。')
else:
    st.info(f'真实模型模式：{config.LLM_MODEL}。请勿输入密码、个人信息或未脱敏日志；提交内容将发送至配置的模型服务。')

def attempt(task, function, **inputs):
    with st.status('检查输入…', expanded=False) as indicator:
        def progress(event):
            label = STAGES.get(event['kind'])
            if label:
                if event['kind'] == 'model_request' and event.get('mock'):
                    label = '演示模式：准备资料预览'
                indicator.update(label=label + '…')
        result, row = run_test(task, function, inputs, progress)
        label = '请求失败' if row['error'] else '处理完成'
        indicator.update(label=f"{label} · 总耗时 {row['elapsed_seconds']:.2f} 秒",
                         state='error' if row['error'] else 'complete', expanded=False)
    history = st.session_state.setdefault('test_runs', [])
    history.append(row)
    st.session_state.test_runs = history[-50:]
    if row['error']:
        st.error(row['error']['message'])
    return result

def fill_example(name):
    if name == 'explain':
        q = ui_examples.explanation_example()
        st.session_state.question = q
        st.session_state['choice_' + q.question_id] = 'B'
        st.session_state.example_question = True
        st.session_state.pop('assessment_result', None)
        return
    values = {'learning': ui_examples.LEARNING, 'next_step': ui_examples.NEXT,
              'debug': ui_examples.DEBUG, 'generate': ui_examples.GENERATE}[name]
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
    with st.expander('资料来源', expanded=False):
        if not evidence:
            st.caption('没有可核对的引用。')
        for e in evidence:
            st.write(f'{e.source_label} [{e.source_id}]')
            if e.source_pages:
                st.caption('页码：' + ', '.join(map(str, e.source_pages)))
            if e.url:
                st.link_button('查看官方资料', e.url)
            if e.product:
                st.caption(f'{e.product} · {e.version or "版本未指定"} · 核对日期 {e.checked_on or "未记录"}')
            st.write(e.text)

def status(result):
    labels = {'ANSWERED': '已回答', 'GENERATED': '已生成', 'INSUFFICIENT_EVIDENCE': '资料不足',
              'NEED_MORE_INFORMATION': '需要补充信息', 'OUT_OF_SCOPE': '超出当前范围',
              'NEEDS_REVIEW': '需要复核，暂不判分', 'UNSUPPORTED_TOPIC': '暂不支持该知识点'}
    render = st.success if result.status in {'ANSWERED', 'GENERATED'} else st.warning
    render(labels.get(result.status, result.status))
    for item in getattr(result, 'need_more_information', []):
        st.write('请补充：' + item)
    if getattr(result, 'reason', ''):
        st.write(result.reason)

try:
    catalog = exercise_catalog()
    counts = {t: len(load([t])) for t in ('concept', 'task', 'question', 'official')}
except (ValueError, OSError):
    st.error('课程数据无法读取，请先运行数据检查。')
    st.stop()
with st.sidebar:
    st.header('知识库状态')
    st.write(f"概念 {counts['concept']} · 任务 {counts['task']} · 例题 {counts['question']} · 官方资料 {counts['official']}")
    st.caption('9 道例题的答案仍待人工核对；系统仅参考其出题形式。')

t1, t2, t3 = st.tabs(['1 · 知识问答', '2 · 操作与 Debug', '3 · 模拟题与详解'])
with t1:
    st.button('填入知识问答示例', on_click=fill_example, args=('learning',))
    with st.form('learning_form'):
        question = st.text_area('你的问题', placeholder='例如：为什么修改 DataTable 后还需要写回表格？', max_chars=12000, key='learn_question')
        week = st.selectbox('课程 Week', ['不限', 1, 2, 3, 4, 5], key='learn_week')
        depth = st.selectbox('讲解详细程度', ['Brief', 'Detailed'], key='learn_depth')
        ask = st.form_submit_button('提问')
    if ask:
        st.session_state.learning = attempt('learning', answer_concept_question, question=question, week=None if week == '不限' else week, depth=depth)
    r = st.session_state.get('learning')
    if r:
        status(r)
        st.write(r.answer)
        if r.key_concept:
            st.caption('知识点：' + r.key_concept)
        if r.exercise_connection:
            st.write('练习联系：', r.exercise_connection)
        if r.common_misunderstanding:
            st.write('常见误解：', r.common_misunderstanding)
        sources(r.evidence)
with t2:
    sample_next, sample_debug = st.columns(2)
    sample_next.button('填入下一步示例', on_click=fill_example, args=('next_step',))
    sample_debug.button('填入 Debug 示例', on_click=fill_example, args=('debug',))
    w = st.selectbox('练习 Week', list(catalog), key='build_week')
    ex = st.selectbox('课堂练习', catalog[w], key=f'exercise_{w}')
    mode = st.radio('需要哪种帮助？', ['下一步', 'Debug'], horizontal=True, key='help_mode')
    with st.form('practice_form'):
        if mode == '下一步':
            last = st.text_input('最后完成的操作', max_chars=12000, key='next_last')
            state = st.text_area('当前界面或结果', max_chars=12000, key='next_state')
        else:
            activity = st.text_input('Activity 名称', max_chars=1000, key='debug_activity')
            error = st.text_area('错误消息，或预期结果与实际结果的差别', max_chars=12000, key='debug_error')
            change = st.text_input('最近修改（可选）', max_chars=4000, key='debug_change')
        build = st.form_submit_button('获取指导')
    context = (w, ex, mode)
    if build:
        r = (attempt('next_step', get_next_step, week=w, exercise=ex, last_completed_step=last, current_state=state)
             if mode == '下一步' else attempt('debug', debug_workflow, week=w, exercise=ex, activity=activity, error_message=error, recent_change=change))
        st.session_state.build_result = (context, r)
    stored = st.session_state.get('build_result')
    if stored and stored[0] == context and stored[1]:
        r = stored[1]
        status(r)
        if mode == '下一步':
            st.write(r.where_you_are)
            for i, action in enumerate(r.next_actions, 1):
                st.write(f'{i}. {action}')
            if r.activity_or_expression:
                st.code('\n'.join(r.activity_or_expression), language=None)
            if r.expected_result:
                st.write('预期结果：', r.expected_result)
            if r.common_mistake:
                st.write('注意：', r.common_mistake)
        else:
            categories = {'EXERCISE_STEP': '步骤配置', 'WORKFLOW_LOGIC': '流程逻辑',
                          'ENVIRONMENT_SETUP': '环境与连接', 'PLATFORM_VERSION': '平台版本',
                          'INSUFFICIENT_INFORMATION': '信息不足'}
            st.caption('问题类别 · ' + categories.get(r.diagnosis_type, r.diagnosis_type))
            if r.possible_causes:
                st.caption('以下是待验证的排查方向，并非已确认的根因。先检查第一项，未解决再展开其他原因。')
                first = r.possible_causes[0]
                with st.container(border=True):
                    st.markdown('### 01 · 优先检查')
                    st.write(first.cause)
                    st.markdown('**先检查什么**')
                    st.write(first.check)
                    st.markdown('**确认后如何修复**')
                    st.write(first.fix)
                    if first.rationale:
                        with st.expander('为什么先检查这一项'):
                            st.write(first.rationale)
                if len(r.possible_causes) > 1:
                    st.markdown('#### 其他可能原因')
                    for i, c in enumerate(r.possible_causes[1:], 2):
                        with st.expander(f'排查方向 {i} · 第一项未解决时查看'):
                            st.write(c.cause)
                            st.markdown('**检查方法**')
                            st.write(c.check)
                            st.markdown('**确认后如何修复**')
                            st.write(c.fix)
                            if c.rationale:
                                st.markdown('**判断依据**')
                                st.write(c.rationale)
        if r.verification:
            with st.container(border=True):
                st.markdown('#### 修复后验证' if mode == 'Debug' else '#### 完成后验证')
                st.write(r.verification)
        sources(r.evidence)
with t3:
    st.caption('生成的是学习练习，不是考试预测。题目与解析仍需结合原资料核对。')
    sample_gen, sample_explain = st.columns(2)
    sample_gen.button('填入出题示例', on_click=fill_example, args=('generate',))
    sample_explain.button('载入讲题示例', on_click=fill_example, args=('explain',))
    st.caption('示例按钮只填入内容，不调用模型。讲题示例会载入一道固定开发测试题，提交答案后才请求讲解。')
    with st.form('generate_form'):
        topic = st.text_input('想练习的知识点', placeholder='例如：DataTable、Regex、Anchor', max_chars=1000, key='gen_topic')
        diff = st.selectbox('难度', ['Easy', 'Medium', 'Hard'], index=1, key='gen_difficulty')
        qt = st.selectbox('题型', ['Concept Distinction', 'Workflow Logic', 'Activity Selection', 'Error Diagnosis', 'Activity Placement', 'Output Prediction'], key='gen_type')
        generate = st.form_submit_button('生成题目')
    if generate:
        st.session_state.question = attempt('generate', generate_question, topic=topic, difficulty=diff, question_type=qt)
        st.session_state.example_question = False
        st.session_state.pop('assessment_result', None)
    q = st.session_state.get('question')
    if q:
        status(q)
        if q.status == 'GENERATED':
            if not st.session_state.get('example_question') and q.review_status == 'NEEDS_HUMAN_REVIEW':
                st.warning('这是 AI 生成的练习题草稿，需要逐题人工复核后再正式使用。')
            if st.session_state.get('example_question'):
                st.caption('固定讲题示例 · 开发测试题，非教师例题，也不是本次 AI 生成的题目。已预选 B，可修改后提交。')
            with st.container(key='practice_question_card'):
                with st.form('answer_' + q.question_id, border=False):
                    st.markdown(
                        '<div class="question-eyebrow">练习题 · QUESTION</div>'
                        '<div class="question-stem">'
                        + escape(q.question) + '</div>', unsafe_allow_html=True,
                    )
                    answer = st.radio('选择答案', list(q.options), index=None, format_func=lambda k: f'{k}. {q.options[k]}', key='choice_' + q.question_id)
                    submit = st.form_submit_button('提交答案')
            if submit:
                if answer is None:
                    st.warning('请先选择答案。')
                else:
                    explanation = attempt('explain', explain_question, question=q, user_answer=answer)
                    st.session_state.assessment_result = (q.question_id, answer, explanation)
            saved = st.session_state.get('assessment_result')
            if saved and saved[0] == q.question_id and saved[2]:
                _, submitted_answer, exp = saved
                st.markdown('### 答案解析')
                st.caption('上次提交的答案：' + submitted_answer)
                status(exp)
                if exp.status == 'ANSWERED':
                    if submitted_answer == exp.correct_answer:
                        st.success('回答正确')
                    else:
                        st.info('正确答案：' + exp.correct_answer)
                    st.write(exp.why_correct)
                    for k, value in exp.why_others_wrong.items():
                        st.write(f'{k}：{value}')
                    st.write('学习要点：', exp.learning_takeaway)
                    if exp.student_misunderstanding:
                        st.write('可复习的地方：', exp.student_misunderstanding)
                sources(exp.evidence)
                sources([evidence_for(c) for c in by_ids(q.course_evidence_ids)])

st.divider()
with st.expander('测试与导出', expanded=False):
    st.caption('当前为 C 版功能测试。记录只保存在当前浏览器会话，最多保留最近 50 条；刷新断线或重启可能丢失，请及时下载。')
    st.caption('导出包含题目答案、输入和资料引用，不含 API 密钥或请求头。日志脱敏不能识别所有个人信息，分享前请自行复核。')
    rows = st.session_state.get('test_runs', [])
    if not rows:
        st.info('还没有测试记录。填入示例后点击提交，记录会自动出现在这里。')
    else:
        st.dataframe([{'记录': r['run_id'], '行为': r['task_label'], '版本': r['prompt_version'],
                       '模式': '演示' if r['mock'] else '真实模型',
                       '状态': 'ERROR' if r['error'] else r['output'].get('status', ''),
                       '耗时（秒）': r['elapsed_seconds']} for r in rows], hide_index=True)
        selected_id = st.selectbox('查看一条记录', [r['run_id'] for r in reversed(rows)], key='export_selection')
        selected = next(r for r in rows if r['run_id'] == selected_id)
        st.caption(f"{selected['task_label']} · {selected['prompt_version']} · 总耗时 {selected['elapsed_seconds']:.2f} 秒")
        st.text('处理阶段：' + ' → '.join(s['label'] for s in selected['stages']))
        st.json(selected, expanded=False)
        download_one, download_all = st.columns(2)
        download_one.download_button('下载本条记录（JSON）', export_json([selected]), file_name=f"C_test_{selected_id}.json", mime='application/json', on_click='ignore')
        download_all.download_button('下载全部记录（JSON）', export_json(rows), file_name='C_function_tests.json', mime='application/json', on_click='ignore')
        st.download_button('下载全部记录（Markdown，发组员）', export_markdown(rows), file_name='C_function_tests.md', mime='text/markdown', on_click='ignore')

render_footer()
