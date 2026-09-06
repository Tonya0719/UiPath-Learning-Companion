from schemas.outputs import NextStepAnswer, DebugAnswer
from retrieval.retriever import retrieve, task_context, exercise_catalog
from runtime import variant
from llm_client import call_model
from modules.common import unique, ground, official_support, limited, language_of, localized

def valid_exercise(week, exercise):
    return exercise in exercise_catalog().get(week, [])

def get_next_step(week, exercise, last_completed_step, current_state):
    language = language_of(last_completed_step, current_state, exercise)
    if not valid_exercise(week, exercise):
        return NextStepAnswer(status='OUT_OF_SCOPE', need_more_information=[localized(
            language, '请选择 Week 1–4 中对应的课堂练习。',
            'Please select the corresponding Week 1–4 classroom exercise.')])
    last_completed_step, current_state = limited(last_completed_step), limited(current_state)
    if not last_completed_step or not current_state:
        return NextStepAnswer(status='NEED_MORE_INFORMATION', need_more_information=[localized(
            language, '请说明最后完成的操作和当前界面/结果。',
            'Please describe the last completed action and the current screen or result.')])
    cards = task_context(last_completed_step + ' ' + current_state, week, exercise)
    if variant.get() == 'C' and not cards:
        return NextStepAnswer(status='INSUFFICIENT_EVIDENCE', need_more_information=[localized(
            language, '未定位到步骤，请提供 activity 名称或具体操作。',
            'The step could not be located. Please provide the activity name or exact action.')])
    demo = {'status': 'NEED_MORE_INFORMATION', 'where_you_are': '演示模式只展示相关资料，不自动判定你完成了哪一步。',
            'need_more_information': ['请配置真实模型以获得下一步判断。'], 'evidence': [{'source_id': c['id']} for c in cards]}
    result = call_model('next_step', dict(week=week, exercise=exercise, last_completed_step=last_completed_step, current_state=current_state), cards, NextStepAnswer, demo)
    return ground(result, cards, language)

def debug_workflow(week, exercise, activity, error_message, recent_change=''):
    language = language_of(activity, error_message, recent_change, exercise)
    if not valid_exercise(week, exercise):
        return DebugAnswer(status='OUT_OF_SCOPE', need_more_information=[localized(
            language, '请选择 Week 1–4 中对应的课堂练习。',
            'Please select the corresponding Week 1–4 classroom exercise.')])
    activity, error_message, recent_change = map(limited, (activity, error_message, recent_change))
    if not activity or not error_message:
        return DebugAnswer(status='NEED_MORE_INFORMATION', need_more_information=[localized(
            language, '请提供 activity，以及错误消息或“预期结果与实际结果”的差别。',
            'Please provide the activity and either the error message or the difference between expected and actual results.')])
    query = activity + ' ' + error_message + ' ' + recent_change
    cards = unique(retrieve(query, ['task'], week=week, exercise=exercise, top_k=3)
                   + retrieve(query, ['concept'], week=week, top_k=2) + official_support(query))
    if variant.get() == 'C' and not cards:
        return DebugAnswer(status='INSUFFICIENT_EVIDENCE', need_more_information=[localized(
            language, '未找到对应资料，请补充完整错误和环境说明。',
            'No matching course evidence was found. Please provide the complete error and environment details.')])
    demo = {'status': 'NEED_MORE_INFORMATION', 'need_more_information': ['演示模式只预览相关资料，不确认根因。请配置真实模型。'],
            'evidence': [{'source_id': c['id']} for c in cards]}
    result = call_model('debug', dict(week=week, exercise=exercise, activity=activity, error_message=error_message, recent_change=recent_change), cards, DebugAnswer, demo)
    return ground(result, cards, language)
