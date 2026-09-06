from schemas.outputs import NextStepAnswer, DebugAnswer
from retrieval.retriever import retrieve, task_context, exercise_catalog
from runtime import variant
from llm_client import call_model
from modules.common import unique, ground, official_support, limited, language_of
from ui_locale import tr


def valid_exercise(week, exercise):
    return exercise in exercise_catalog().get(week, [])


def get_next_step(week, exercise, last_completed_step, current_state):
    language = language_of(last_completed_step, current_state, exercise)
    if not valid_exercise(week, exercise):
        return NextStepAnswer(status='OUT_OF_SCOPE', need_more_information=[tr(language, 'please_select_exercise')])
    last_completed_step, current_state = limited(last_completed_step), limited(current_state)
    if not last_completed_step or not current_state:
        return NextStepAnswer(status='NEED_MORE_INFORMATION', need_more_information=[tr(language, 'describe_step_state')])
    cards = task_context(last_completed_step + ' ' + current_state, week, exercise)
    if variant.get() == 'C' and not cards:
        return NextStepAnswer(status='INSUFFICIENT_EVIDENCE', need_more_information=[tr(language, 'step_not_located')])
    demo = {
        'status': 'NEED_MORE_INFORMATION',
        'where_you_are': tr(language, 'demo_previews_only'),
        'need_more_information': [tr(language, 'configure_real_model_next')],
        'evidence': [{'source_id': c['id']} for c in cards],
    }
    result = call_model('next_step', dict(
        week=week,
        exercise=exercise,
        last_completed_step=last_completed_step,
        current_state=current_state,
    ), cards, NextStepAnswer, demo)
    return ground(result, cards, language)


def debug_workflow(week, exercise, activity, error_message, recent_change=''):
    language = language_of(activity, error_message, recent_change, exercise)
    if not valid_exercise(week, exercise):
        return DebugAnswer(status='OUT_OF_SCOPE', need_more_information=[tr(language, 'please_select_exercise')])
    activity, error_message, recent_change = map(limited, (activity, error_message, recent_change))
    if not activity or not error_message:
        return DebugAnswer(status='NEED_MORE_INFORMATION', need_more_information=[tr(language, 'complete_error_environment')])
    query = activity + ' ' + error_message + ' ' + recent_change
    cards = unique(retrieve(query, ['task'], week=week, exercise=exercise, top_k=3)
                   + retrieve(query, ['concept'], week=week, top_k=2) + official_support(query))
    if variant.get() == 'C' and not cards:
        return DebugAnswer(status='INSUFFICIENT_EVIDENCE', need_more_information=[tr(language, 'no_matching_evidence')])
    demo = {
        'status': 'NEED_MORE_INFORMATION',
        'need_more_information': [tr(language, 'demo_previews_only')],
        'evidence': [{'source_id': c['id']} for c in cards],
    }
    result = call_model('debug', dict(
        week=week,
        exercise=exercise,
        activity=activity,
        error_message=error_message,
        recent_change=recent_change,
    ), cards, DebugAnswer, demo)
    return ground(result, cards, language)
