from schemas.outputs import LearningAnswer
from retrieval.retriever import retrieve
from runtime import variant
from llm_client import call_model
from modules.common import official_support, unique, ground, limited, language_of, localized

def answer_concept_question(question, week=None, topic=None, depth='Brief'):
    question = limited(question)
    language = language_of(question, topic)
    if not question:
        return LearningAnswer(status='NEED_MORE_INFORMATION', need_more_information=[localized(
            language, '你想了解哪个知识点？', 'Which concept would you like to understand?')])
    if week is not None and week not in range(1, 6):
        return LearningAnswer(status='OUT_OF_SCOPE', answer=localized(
            language, '当前支持 Weeks 1–5。', 'The current scope supports Weeks 1–5.'))
    cards = unique(retrieve(question, ['concept', 'task'], week=week, topic=topic, top_k=4) + official_support(question))
    if variant.get() == 'C' and not cards:
        return LearningAnswer(status='INSUFFICIENT_EVIDENCE', answer=localized(
            language, '暂未找到足够相关的资料。', 'Not enough relevant course evidence was found.'),
            need_more_information=[localized(language,
                '请补充 Week、英文 activity 名称或更具体的问题。',
                'Please add the Week, exact activity name, or a more specific question.')])
    demo = {'status': 'ANSWERED', 'answer': localized(language, '【资料预览，非 AI 回答】', '[Evidence preview, not an AI answer]') + '\n' + '\n'.join(c.get('concept') or c.get('goal') or c.get('content', '') for c in cards[:2]),
            'key_concept': cards[0].get('topic', '') if cards else '',
            'exercise_connection': next((c['exercise_connection'] for c in cards if c.get('exercise_connection')), None),
            'common_misunderstanding': next(('; '.join(c['common_errors']) for c in cards if c.get('common_errors')), None),
            'evidence': [{'source_id': c['id']} for c in cards[:2]]}
    result = call_model('learning', {'question': question, 'week': week, 'topic': topic, 'depth': depth}, cards, LearningAnswer, demo)
    return ground(result, cards, language)
