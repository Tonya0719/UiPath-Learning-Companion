import uuid
from difflib import SequenceMatcher
from schemas.outputs import PracticeQuestion, QuestionExplanation
from retrieval.retriever import retrieve, by_ids, load, topic_relevance
from runtime import variant, record
from llm_client import call_model
from modules.common import ground, limited, language_of, localized

def generate_question(topic, difficulty='Medium', question_type='Workflow Logic'):
    topic = limited(topic)
    language = language_of(topic)
    if not topic:
        return PracticeQuestion(status='UNSUPPORTED_TOPIC', reason=localized(
            language, '请先填写知识点。', 'Please enter a topic.'),
            difficulty=difficulty, question_type=question_type)
    course = retrieve(topic, ['concept', 'task'], topic=topic, top_k=5)
    refs = retrieve(topic + ' ' + question_type, ['question'], top_k=3)
    # These answers are unverified. Only style fields are exposed to the generator.
    styles = [{k: c[k] for k in ('id', 'question', 'options', 'tested_skill', 'question_form', 'question_type') if k in c} for c in refs]
    if variant.get() == 'C' and not course:
        return PracticeQuestion(status='UNSUPPORTED_TOPIC', reason=localized(
            language, '没有找到支持该知识点的课程资料。',
            'No course evidence supports this topic.'),
            difficulty=difficulty, question_type=question_type)
    demo = {'status': 'NEEDS_REVIEW', 'reason': '演示模式不生成或批改试题。9 道教师例题已接入检索，请配置真实模型后出题。'}
    generation_course = course
    if variant.get() == 'C' and course:
        relevance = {c['id']: topic_relevance(topic, c) for c in course}
        best = max(relevance.values(), default=0.0)
        direct_ids = {ident for ident, score in relevance.items()
                      if score >= max(0.5, best - 0.15)}
        direct_course = [c for c in course if c['id'] in direct_ids]
        if direct_course:
            generation_course = direct_course
        record('direct_topic_evidence', topic=topic,
               direct_ids=[c['id'] for c in generation_course],
               adjacent_ids=[c['id'] for c in course if c not in generation_course])
    result = call_model('generate', dict(topic=topic, difficulty=difficulty, question_type=question_type), generation_course, PracticeQuestion, demo, styles)
    if result.status != 'GENERATED':
        result.difficulty, result.question_type = difficulty, question_type
        return result
    valid_course, valid_refs = {c['id'] for c in generation_course}, {c['id'] for c in refs}
    if (any(x not in valid_course for x in result.course_evidence_ids)
        or any(x not in valid_refs for x in result.reference_question_ids)
        or (variant.get() == 'C' and not result.course_evidence_ids)):
        return PracticeQuestion(status='NEEDS_REVIEW', reason=localized(
            language, '题目引用未通过核对，暂不展示。',
            'The question citations did not pass validation and the item is withheld.'),
            difficulty=difficulty, question_type=question_type)
    if variant.get() == 'C':
        relevance = {c['id']: topic_relevance(topic, c) for c in generation_course}
        best = max(relevance.values(), default=0.0)
        direct_ids = {ident for ident, score in relevance.items() if score >= max(0.5, best - 0.15)}
        if not direct_ids.intersection(result.course_evidence_ids):
            return PracticeQuestion(status='NEEDS_REVIEW', reason=localized(
                language, '题目引用的是相邻知识点，未通过主题一致性检查。',
                'The question cites a neighbouring concept and failed the topic-alignment check.'),
                difficulty=difficulty, question_type=question_type)
    # Mechanical near-copy check; semantic novelty still needs human evaluation.
    if variant.get() == 'C':
        for ref in load(['question']):
            if SequenceMatcher(None, result.question.casefold(), ref['question'].casefold()).ratio() > 0.82:
                return PracticeQuestion(status='NEEDS_REVIEW', reason=localized(
                    language, '题目与教师例题过于相似，请重新生成。',
                    'The question is too similar to a teacher example and must be regenerated.'),
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
        return QuestionExplanation(status='NEEDS_REVIEW', reason=localized(
            language, '该题尚未通过生成检查。', 'This question has not passed generation checks.'))
    if user_answer is not None and user_answer not in question.options:
        return QuestionExplanation(status='NEED_MORE_INFORMATION', reason=localized(
            language, '请选择 A–D 中的一个选项。', 'Please select one option from A–D.'))
    # Preserve the evidence used for generation; do not silently replace it.
    cards = by_ids(question.course_evidence_ids)
    if variant.get() == 'C' and (not cards or len(cards) != len(set(question.course_evidence_ids))):
        return QuestionExplanation(status='INSUFFICIENT_EVIDENCE', reason=localized(
            language, '出题时的课程依据缺失，暂不判分。',
            'The course evidence used to generate the question is missing, so no answer is graded.'))
    demo = {'status': 'NEEDS_REVIEW', 'reason': '演示模式不判断答案，请配置真实模型。'}
    result = call_model('explain', {'question': question.model_dump(), 'user_answer': user_answer}, cards, QuestionExplanation, demo)
    if result.status == 'ANSWERED':
        if (result.correct_answer != question.correct_answer
            or set(result.why_others_wrong) != set(question.options) - {question.correct_answer}
            or not result.why_correct.strip()
            or any(not str(v).strip() for v in result.why_others_wrong.values())):
                return QuestionExplanation(status='NEEDS_REVIEW', reason=localized(
                    language, '答案与逐项解释未通过一致性检查，暂不判分。',
                    'The answer and option explanations failed consistency checks, so no answer is graded.'))
    return ground(result, cards, language)
