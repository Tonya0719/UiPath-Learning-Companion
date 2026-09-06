"""Strict metadata + lexical retrieval, not BM25/embedding retrieval."""
import json
import math
import re
from collections import Counter
from config import DATA_DIR
from runtime import variant, record
DATA = DATA_DIR
MAP = {'concept': 'concept_cards.json', 'task': 'task_cards.json', 'question': 'question_cards.json', 'official': 'official_cards.json'}
ALIASES = {
    '机器人流程自动化': 'rpa', '自动化': 'automation', '人工智能': 'ai',
    '锚点': 'anchor', '选择器': 'selector', '变量': 'variable', '参数': 'argument',
    '数据表': 'datatable', '表格': 'spreadsheet', '行号': 'row index', '索引': 'index',
    '发票': 'invoice', '覆盖': 'overwrite', '追加': 'append', '清空': 'clear delete range',
    '重复': 'duplicate', '循环': 'loop for each', '正则': 'regex', '邮件': 'email',
    '数据验证': 'data validation', '文档提取': 'document data extraction',
    '无人值守': 'unattended', '有人值守': 'attended', '报错': 'error',
    '用户名': 'username', '密码': 'password', '登录': 'login', '按钮': 'click',
    '读范围': 'read range', '写范围': 'write range', '空值': 'empty null',
    '审批': 'approval', '预约': 'appointment', '报销': 'claims',
}
STOP = set('a an the is are to of in on for and or why what how do does i my it this that please help me'.split())

def normalize(value):
    value = str(value).lower()
    for key in sorted(ALIASES, key=len, reverse=True):
        value = value.replace(key, ' ' + ALIASES[key] + ' ')
    return value

def tok(value):
    return [t for t in re.findall(r'[a-z0-9_]+|[\u4e00-\u9fff]+', normalize(value)) if t not in STOP]

def load(types=None):
    cards = []
    for kind in types if types is not None else MAP:
        path = DATA / MAP[kind]
        if not path.exists():
            if kind == 'official':
                continue
            raise ValueError(f'Missing data file: {path.name}')
        rows = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(rows, list):
            raise ValueError(f'{path.name} must contain a list')
        cards.extend({**c, 'type': c.get('type', kind)} for c in rows)
    return cards

def flatten(value):
    if isinstance(value, dict):
        return ' '.join(flatten(x) for x in value.values())
    if isinstance(value, list):
        return ' '.join(flatten(x) for x in value)
    return str(value or '')

def text(card):
    fields = ('topic', 'topic_aliases', 'subtopic', 'concept', 'rules', 'comparison', 'useful_patterns',
              'common_errors', 'exercise_connection', 'goal', 'procedure', 'activity_names',
              'expected_result', 'trigger_symptom', 'known_failures', 'diagnostic_checks',
              'question', 'knowledge_point', 'tested_skill', 'question_form', 'question_type', 'content',
              'scope_notes')
    return ' '.join(flatten(card.get(k)) for k in fields)

def _topic_terms(value):
    stems = {'writing': 'write', 'written': 'write', 'writes': 'write', 'tables': 'table'}
    return {stems.get(term, term) for term in tok(value)}

def topic_relevance(topic, card):
    """Score only topic metadata so neighbouring body text cannot dominate."""
    requested = _topic_terms(topic)
    if not requested:
        return 0.0
    labels = _topic_terms(flatten([
        card.get('topic', ''), card.get('topic_aliases', []), card.get('subtopic', ''),
    ]))
    return len(requested & labels) / len(requested)

def lexical_score(query, doc):
    terms = set(tok(query))
    if not terms:
        return 0.0
    counts = Counter(tok(doc))
    return sum(1 + math.log1p(counts[t]) for t in terms if counts[t]) / len(terms)

def retrieve(query, card_types=None, week=None, topic=None, exercise=None, top_k=5):
    record('retrieval_started')
    if variant.get() != 'C':
        return []
    candidates = []
    for c in load(card_types):
        if week is not None and c.get('week') != week:
            continue
        if exercise and normalize(exercise).strip() != normalize(c.get('exercise', '')).strip():
            continue
        if topic:
            labels = flatten([c.get('topic', ''), c.get('topic_aliases', [])])
            if not set(tok(topic)).intersection(tok(labels)):
                continue
        score = lexical_score(query, text(c)) + (2.0 * topic_relevance(topic, c) if topic else 0.0)
        if score >= 0.2:
            candidates.append({**c, 'retrieval_score': score})
    result = sorted(candidates, key=lambda c: (-c['retrieval_score'], c['id']))[:top_k]
    record('retrieval', query=query, week=week, exercise=exercise, topic=topic,
           ids=[c['id'] for c in result], scores=[c['retrieval_score'] for c in result])
    return result

def by_ids(ids):
    record('evidence_lookup', ids=list(ids))
    if variant.get() != 'C':
        return []
    lookup = {c['id']: c for c in load()}
    return [lookup[x] for x in dict.fromkeys(ids) if x in lookup]

def task_context(query, week, exercise):
    matches = retrieve(query, ['task'], week=week, exercise=exercise, top_k=2)
    if not matches:
        return []
    path = DATA / 'task_sequence.json'
    sequences = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    sequence = next((s['task_ids'] for s in sequences if s['week'] == week and s['exercise'] == exercise), [])
    ids = []
    for card in matches:
        if card['id'] in sequence:
            i = sequence.index(card['id'])
            ids.extend(sequence[max(0, i - 1):i + 2])
        else:
            ids.append(card['id'])
    result = by_ids(ids)
    record('step_context', ids=[c['id'] for c in result])
    return result

def exercise_catalog():
    result = {}
    for c in load(['task']):
        result.setdefault(c['week'], set()).add(c['exercise'])
    return {w: sorted(names) for w, names in sorted(result.items())}
