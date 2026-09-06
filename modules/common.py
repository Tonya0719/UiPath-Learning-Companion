import re
from schemas.outputs import Evidence
from runtime import variant
from retrieval.retriever import retrieve

def official_support(query):
    return retrieve(query, ['official'], top_k=2)

def unique(cards):
    return list({c['id']: c for c in cards}.values())

def language_of(*values):
    """Infer the response language from user-provided text; default to Chinese."""
    text = ' '.join(str(value or '') for value in values)
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'en' if re.search(r'[A-Za-z]', text) else 'zh'

def localized(language, chinese, english):
    return chinese if language == 'zh' else english

def evidence_for(card):
    if card.get('type') == 'task':
        parts = []
        if card.get('goal'):
            parts.append('Goal: ' + card['goal'])
        if card.get('procedure'):
            parts.append('Procedure: ' + '; '.join(card['procedure']))
        text = ' '.join(parts)
    else:
        text = card.get('concept') or card.get('content', '')
    return Evidence(source_id=card['id'], source_label=card.get('source', card['id']),
                    text=text,
                    source_pages=card.get('source_pages', []), url=card.get('url'),
                    product=card.get('product'), version=card.get('version'), checked_on=card.get('checked_on'))

def ground(result, cards, language='zh'):
    """Source metadata is supplied by code, never trusted from model text."""
    lookup = {c['id']: c for c in cards}
    ids = [e.source_id for e in result.evidence]
    invalid = any(i not in lookup for i in ids)
    result.evidence = [evidence_for(lookup[i]) for i in dict.fromkeys(ids) if i in lookup]
    if (invalid or (variant.get() == 'C' and not result.evidence)) and result.status == 'ANSWERED':
        result.status = 'INSUFFICIENT_EVIDENCE'
        if hasattr(result, 'need_more_information'):
            result.need_more_information = [localized(
                language,
                '当前回答缺少可核对的资料引用，请补充课程章节或具体操作。',
                'The answer lacks a verifiable course citation. Please add the course section or exact activity.',
            )]
        if hasattr(result, 'reason'):
            result.reason = localized(
                language,
                '回答引用未通过资料检查，暂不判定答案。',
                'The cited evidence did not pass validation, so no answer is graded.',
            )
        # Hide unsupported actionable content rather than merely attaching a warning.
        for name in ('answer', 'where_you_are', 'expected_result', 'verification', 'why_correct', 'learning_takeaway'):
            if hasattr(result, name):
                setattr(result, name, '')
        for name in ('next_actions', 'possible_causes'):
            if hasattr(result, name):
                setattr(result, name, [])
    return result

def limited(value):
    return str(value).strip()[:12000]
