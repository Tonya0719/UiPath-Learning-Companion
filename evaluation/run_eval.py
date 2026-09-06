"""Dry-run by default. Real evaluation requires explicit --run and reviewed cases."""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from runtime import experiment
from modules.learning_explainer import answer_concept_question
from modules.guided_practice import get_next_step, debug_workflow
from modules.assessment_coach import generate_question, explain_question
from retrieval.retriever import load
from scripts.validate_data import validate

FUNCTIONS = {'learning': answer_concept_question, 'next_step': get_next_step, 'debug': debug_workflow,
             'generate': generate_question, 'explain': explain_question}

def check_cases(cases):
    ids, errors = set(), []
    evidence_ids = {c['id'] for c in load()}
    for c in cases:
        if c.get('case_id') in ids:
            errors.append('Duplicate case ID')
        ids.add(c.get('case_id'))
        if c.get('module') not in FUNCTIONS or not isinstance(c.get('input'), dict):
            errors.append(f"{c.get('case_id')}: invalid module/input")
        if not c.get('expected_behavior'):
            errors.append(f"{c.get('case_id')}: missing expected behavior")
        if not set(c.get('expected_evidence', [])).issubset(evidence_ids):
            errors.append(f"{c.get('case_id')}: unknown expected evidence")
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', type=Path, default=config.ROOT / 'evaluation' / 'cases.json')
    parser.add_argument('--variant', choices=['A', 'B', 'C', 'all'], default='all')
    parser.add_argument('--case-id', action='append', default=[],
                        help='Run only this case ID; repeat the option to select multiple cases')
    parser.add_argument('--run', action='store_true', help='Calls the configured real model; may incur API charges')
    parser.add_argument('--allow-draft', action='store_true', help='Development runs only; not final evaluation')
    args = parser.parse_args()
    all_cases = json.loads(args.cases.read_text(encoding='utf-8'))
    errors = validate()['errors'] + check_cases(all_cases)
    if errors:
        parser.error('; '.join(errors))
    known_ids = {c['case_id'] for c in all_cases}
    unknown_ids = [case_id for case_id in args.case_id if case_id not in known_ids]
    if unknown_ids:
        parser.error('Unknown case ID(s): ' + ', '.join(unknown_ids))
    selected_ids = set(args.case_id)
    cases = [c for c in all_cases if not selected_ids or c['case_id'] in selected_ids]
    reviewed = all(c.get('review_status') == 'approved' for c in cases)
    if not args.run:
        note = ('No model calls. Approved cases are structurally ready for evaluation.' if reviewed
                else 'No model calls. Draft cases require evaluation-team review.')
        print(json.dumps({'dry_run': True, 'case_count': len(cases), 'reviewed': reviewed,
                          'note': note}, indent=2))
        return
    if config.MOCK_LLM or not config.LLM_API_KEY:
        parser.error('Real evaluation requires MOCK_LLM=false and an API key. Mock output is not evaluation evidence.')
    if not reviewed and not args.allow_draft:
        parser.error('Cases are not approved; review first or explicitly use --allow-draft for development.')
    modes = ['A', 'B', 'C'] if args.variant == 'all' else [args.variant]
    folder = config.ROOT / 'evaluation' / 'results'
    folder.mkdir(exist_ok=True)
    output = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.jsonl')
    records = []
    data_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in config.DATA_DIR.glob('*.json')}
    with output.open('x', encoding='utf-8') as stream:
        for mode in modes:
            for c in cases:
                start = time.monotonic()
                row = {'case_id': c['case_id'], 'module': c['module'], 'variant': mode, 'reviewed': reviewed,
                       'model': config.LLM_MODEL, 'temperature': config.LLM_TEMPERATURE,
                       'case': c, 'data_hashes': data_hashes,
                       'rubric_scores': {'correctness': None, 'grounding': None, 'learning_usefulness': None, 'robustness': None}}
                with experiment(mode) as trace:
                    try:
                        row['output'] = FUNCTIONS[c['module']](**c['input']).model_dump()
                    except Exception as exc:
                        row['error'] = type(exc).__name__
                row.update(trace=trace, elapsed_seconds=round(time.monotonic() - start, 3))
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                stream.flush()
                records.append(row)
                print(c['case_id'], mode, 'ERROR' if 'error' in row else 'saved', flush=True)
    json_output = output.with_suffix('.json')
    json_output.write_text(json.dumps({'format_version': 1, 'runs': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved:', output)
    print('Saved:', json_output)

if __name__ == '__main__':
    main()
