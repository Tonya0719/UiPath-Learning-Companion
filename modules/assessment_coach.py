import uuid
from difflib import SequenceMatcher

from schemas.outputs import PracticeQuestion, QuestionExplanation
from retrieval.retriever import retrieve, by_ids, load, topic_relevance
from runtime import variant, record
from llm_client import call_model
from modules.common import ground, limited, language_of
from ui_locale import tr


def generate_question(topic, difficulty='Medium', question_type='Workflow Logic'):
    topic = limited(topic)
    language = language_of(topic)
    if not topic:
        return PracticeQuestion(status='UNSUPPORTED_TOPIC', reason=tr(language, 'please_enter_topic'),
                                difficulty=difficulty, question_type=question_type)
    course = retrieve(topic, ['concept', 'task'], topic=topic, top_k=5)
    refs = retrieve(topic + ' ' + question_type, ['question'], top_k=3)
    # These answers are unverified. Only style fields are exposed to the generator.
    styles = [{k: c[k] for k in ('id', 'question', 'options', 'tested_skill', 'question_form', 'question_type') if k in c} for c in refs]
    if variant.get() == 'C' and not course:
        return PracticeQuestion(status='UNSUPPORTED_TOPIC', reason=tr(language, 'no_course_evidence_supports_topic'),
                                difficulty=difficulty, question_type=question_type)
    demo = {'status': 'NEEDS_REVIEW', 'reason': tr(language, 'demo_not_generate_questions')}
    generation_course = course
    if variant.get() == 'C' and course:
        relevance = {c['id']: topic_relevance(topic, c) for c in course}
        best = max(relevance.values(), default=0.0)
        direct_ids = {ident for ident, score in relevance.items() if score >= max(0.5, best - 0.15)}
        direct_course = [c for c in course if c['id'] in direct_ids]
        if direct_course:
            generation_course = direct_course
        record('direct_topic_evidence', topic=topic,
               direct_ids=[c['id'] for c in generation_course],
               adjacent_ids=[c['id'] for c in course if c not in generation_course])
    result = call_model('generate', dict(topic=topic, difficulty=difficulty, question_type=question_type),
                        generation_course, PracticeQuestion, demo, styles)
    if result.status != 'GENERATED':
        result.difficulty, result.question_type = difficulty, question_type
        return result
    valid_course, valid_refs = {c['id'] for c in generation_course}, {c['id'] for c in refs}
    if (any(x not in valid_course for x in result.course_evidence_ids)
        or any(x not in valid_refs for x in result.reference_question_ids)
        or (variant.get() == 'C' and not result.course_evidence_ids)):
        return PracticeQuestion(status='NEEDS_REVIEW', reason=tr(language, 'question_validation_failed'),
                                difficulty=difficulty, question_type=question_type)
    if variant.get() == 'C':
        relevance = {c['id']: topic_relevance(topic, c) for c in generation_course}
        best = max(relevance.values(), default=0.0)
        direct_ids = {ident for ident, score in relevance.items() if score >= max(0.5, best - 0.15)}
        if not direct_ids.intersection(result.course_evidence_ids):
            return PracticeQuestion(status='NEEDS_REVIEW', reason=tr(language, 'neighboring_concept_failed_alignment'),
                                    difficulty=difficulty, question_type=question_type)
    if variant.get() == 'C':
        for ref in load(['question']):
            if SequenceMatcher(None, result.question.casefold(), ref['question'].casefold()).ratio() > 0.82:
                return PracticeQuestion(status='NEEDS_REVIEW', reason=tr(language, 'too_similar_teacher_example'),
                                        difficulty=difficulty, question_type=question_type)
    result.question_id = 'GEN-' + uuid.uuid4().hex[:12]
    result.difficulty, result.question_type = difficulty, question_type
    result.review_status = 'NEEDS_HUMAN_REVIEW'
    return result


def explain_question(question, user_answer=None):
    if isinstance(question, dict):
        question = PracticeQuestion.model_validate(question)
    language = language_of(question.question, question.knowledge_point)
    if question.status != 'GENERATED':
        return QuestionExplanation(status='NEEDS_REVIEW', reason=tr(language, 'question_not_passed_checks'))
    if user_answer is not None and user_answer not in question.options:
        return QuestionExplanation(status='NEED_MORE_INFORMATION', reason=tr(language, 'select_option_abcd'))
    cards = by_ids(question.course_evidence_ids)
    if variant.get() == 'C' and (not cards or len(cards) != len(set(question.course_evidence_ids))):
        return QuestionExplanation(status='INSUFFICIENT_EVIDENCE', reason=tr(language, 'missing_course_evidence'))
    demo = {'status': 'NEEDS_REVIEW', 'reason': tr(language, 'demo_not_grade_answers')}
    result = call_model('explain', {'question': question.model_dump(), 'user_answer': user_answer}, cards, QuestionExplanation, demo)
    if result.status == 'ANSWERED':
        if (result.correct_answer != question.correct_answer
            or set(result.why_others_wrong) != set(question.options) - {question.correct_answer}
            or not result.why_correct.strip()
            or any(not str(v).strip() for v in result.why_others_wrong.values())):
            return QuestionExplanation(status='NEEDS_REVIEW', reason=tr(language, 'answer_consistency_failed'))
    return ground(result, cards, language)
