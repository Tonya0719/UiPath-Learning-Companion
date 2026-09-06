"""Structural validation, not verification of course facts or answer correctness."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieval.retriever import DATA, MAP, load

def validate():
    errors, seen = [], set()
    counts = {}
    text_fields = {'concept': ['concept'], 'task': ['exercise', 'goal', 'expected_result'],
                   'question': ['question', 'correct_answer', 'answer_source'], 'official': ['content', 'url', 'product', 'version', 'checked_on']}
    arrays = ('topic_aliases', 'rules', 'common_errors', 'procedure', 'activity_names', 'known_failures', 'trigger_symptom', 'diagnostic_checks')
    all_cards = []
    for kind in MAP:
        rows = load([kind])
        counts[kind] = len(rows)
        for c in rows:
            ident = c.get('id', '<missing>')
            if ident in seen:
                errors.append(f'{ident}: duplicate ID')
            seen.add(ident)
            for key in ['id', 'topic', 'source'] + text_fields[kind]:
                if not isinstance(c.get(key), str) or not c[key].strip():
                    errors.append(f'{ident}: invalid {key}')
            if c.get('type') != kind:
                errors.append(f'{ident}: wrong type')
            if kind != 'official' and (type(c.get('week')) is not int or c['week'] not in range(1, 6)):
                errors.append(f'{ident}: invalid week')
            if kind == 'task' and c.get('week') not in range(1, 5):
                errors.append(f'{ident}: unsupported exercise week')
            for key in arrays:
                if key in c and (not isinstance(c[key], list) or any(not isinstance(x, str) for x in c[key])):
                    errors.append(f'{ident}: invalid {key}')
            if kind in {'concept', 'task'}:
                pages = c.get('source_pages')
                if not isinstance(pages, list) or not pages or any(type(p) is not int or p < 1 for p in pages):
                    errors.append(f'{ident}: invalid source_pages')
            if kind == 'task' and not c.get('procedure'):
                errors.append(f'{ident}: missing procedure')
            if kind == 'question':
                options = c.get('options', {})
                if not isinstance(options, dict) or set(options) != set('ABCD') or c.get('correct_answer') not in options:
                    errors.append(f'{ident}: invalid question options/answer')
                if type(c.get('answer_verified')) is not bool:
                    errors.append(f'{ident}: answer_verified must be boolean')
            if kind == 'official' and not c.get('url', '').startswith('https://docs.uipath.com/'):
                errors.append(f'{ident}: official URL must be UiPath Docs')
            all_cards.append(c)
    lookup = {c['id']: c for c in all_cards}
    sequences = json.loads((DATA / 'task_sequence.json').read_text(encoding='utf-8'))
    sequence_ids = []
    for s in sequences:
        for ident in s['task_ids']:
            c = lookup.get(ident, {})
            if c.get('type') != 'task' or c.get('week') != s['week'] or c.get('exercise') != s['exercise']:
                errors.append(f'{ident}: invalid sequence mapping')
            sequence_ids.append(ident)
    if len(sequence_ids) != len(set(sequence_ids)) or set(sequence_ids) != {c['id'] for c in all_cards if c['type'] == 'task'}:
        errors.append('Sequence must cover each task exactly once')
    return {'counts': counts, 'errors': errors, 'unverified_question_answers': sum(c.get('type') == 'question' and not c.get('answer_verified') for c in all_cards)}

if __name__ == '__main__':
    report = validate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(bool(report['errors']))
