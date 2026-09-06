"""Session-local test records with an allowlisted, secret-redacted export format."""

import json
import re
import time
import uuid
from datetime import datetime, timezone

import config
from runtime import experiment, observe, record
from prompts.templates import prompt_version
from llm_client import thinking_options, ModelError
from pydantic import ValidationError
from retrieval.retriever import load
from modules.common import evidence_for
from ui_locale import TASK_LABELS as LOCALE_TASK_LABELS, STAGE_LABELS as LOCALE_STAGE_LABELS, tr

TASK_LABELS = LOCALE_TASK_LABELS["zh"]
STAGES = LOCALE_STAGE_LABELS["zh"]


def _task_labels(language):
    return LOCALE_TASK_LABELS.get(language, LOCALE_TASK_LABELS["zh"])


def _stage_labels(language):
    return LOCALE_STAGE_LABELS.get(language, LOCALE_STAGE_LABELS["zh"])


def clean(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump()
    if isinstance(value, dict):
        return {
            str(k): '[REDACTED]'
            if any(word in str(k).lower() for word in ('api_key', 'authorization', 'password', 'secret', 'access_token'))
            else clean(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, str):
        if config.LLM_API_KEY:
            value = value.replace(config.LLM_API_KEY, '[REDACTED]')
        value = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', value)
        value = re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[REDACTED]', value)
        return value
    return value


def run_test(task, function, inputs, callback=None, language='zh'):
    begin = time.perf_counter()
    result, error = None, None
    with experiment('C') as events, observe(callback):
        record('input_validation')
        try:
            result = function(**inputs)
            record('result_ready')
        except (ModelError, ValidationError, ValueError, OSError) as exc:
            error = {'type': type(exc).__name__, 'message': (
                'Request did not complete. Check the model configuration, network connection, or data format.'
                if language == 'en' else '请求未完成，请检查模型配置、网络或数据格式。'
            )}
            record('request_failed', error_type=type(exc).__name__)
    duration = round(time.perf_counter() - begin, 3)
    ids = list(dict.fromkeys(
        i for e in events if e['kind'] in {'retrieval', 'step_context', 'evidence_lookup'} for i in e.get('ids', [])
    ))
    snapshots = []
    try:
        lookup = {c['id']: c for c in load()}
        snapshots = [evidence_for(lookup[i]).model_dump() for i in ids if i in lookup]
    except (ValueError, OSError):
        pass
    stages = [{k: e[k] for k in ('kind', 'elapsed_seconds', 'attempt', 'http_status') if k in e}
              for e in events if e['kind'] in _stage_labels(language)]
    stage_labels = _stage_labels(language)
    for stage in stages:
        stage['label'] = stage_labels[stage['kind']]
    row = clean({
        'run_id': uuid.uuid4().hex[:12],
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'task': task,
        'task_label': _task_labels(language)[task],
        'variant': 'C',
        'mock': config.MOCK_LLM,
        'model': config.LLM_MODEL,
        'prompt_version': prompt_version('C'),
        'temperature_requested': config.LLM_TEMPERATURE,
        'thinking_options': thinking_options(task),
        'input': inputs,
        'output': result.model_dump() if result is not None else None,
        'error': error,
        'elapsed_seconds': duration,
        'stages': stages,
        'retrieved_evidence': snapshots,
        'model_response_count': sum(e['kind'] == 'model_response' for e in events),
        'format_retries': sum(e['kind'] == 'format_retry' for e in events),
        'transport_retries': sum(e['kind'] == 'transport_retry' for e in events),
        'review_status': 'unreviewed',
        'review_note': '',
        'notice': (
            'Development feature test record, not an official A/B/C evaluation; demo results do not represent model performance.'
            if language == 'en'
            else '开发功能测试记录，不是正式 A/B/C 评估；演示结果不代表模型效果。'
        ),
    })
    return result, row


def export_json(rows, language='zh'):
    return json.dumps(clean({'format_version': 1, 'runs': rows}), ensure_ascii=False, indent=2)


def export_markdown(rows, language='zh'):
    parts = [
        '# C Variant Feature Test Records' if language == 'en' else '# C 版功能测试记录',
        '',
        'Development records, not manually graded. `mock=true` indicates demo mode and does not represent model quality.'
        if language == 'en'
        else '开发记录，未进行人工评分。`mock=true` 表示演示模式，不代表模型效果。',
        'Please review sensitive information before sharing; the records include question answers and citations.'
        if language == 'en'
        else '请复核隐私信息后再分享；记录包含题目答案和引用。',
        '',
    ]
    for r in clean(rows):
        parts.extend([
            f"## {r['task_label']} · {r['run_id']}",
            '',
            f"Time: {r['created_at_utc']}  " if language == 'en' else f"时间：{r['created_at_utc']}  ",
            f"Variant: {r['variant']} / {r['prompt_version']} · Model: {r['model']} · Demo: {r['mock']}  "
            if language == 'en'
            else f"版本：{r['variant']} / {r['prompt_version']} · 模型：{r['model']} · 演示：{r['mock']}  ",
            f"Total time: {r['elapsed_seconds']:.2f}s · Format retries: {r['format_retries']} · Transport retries: {r['transport_retries']}"
            if language == 'en'
            else f"总耗时：{r['elapsed_seconds']:.2f} 秒 · 格式修复：{r['format_retries']} 次 · 接口重试：{r['transport_retries']} 次",
            '',
        ])
        for title, obj in [
            ('Input' if language == 'en' else '输入', r['input']),
            ('Answer' if language == 'en' else '回答', r['output']),
            ('Error' if language == 'en' else '异常', r['error']),
            ('Retrieved evidence' if language == 'en' else '检索证据', r['retrieved_evidence']),
            ('Stages' if language == 'en' else '处理阶段', r['stages']),
        ]:
            if obj is not None:
                body = json.dumps(obj, ensure_ascii=False, indent=2)
                fence = '`' * max(3, max((len(m.group()) + 1 for m in re.finditer(r'`+', body)), default=3))
                parts.extend([f'### {title}', '', fence + 'json', body, fence, ''])
        parts.extend([
            'Human review note:' if language == 'en' else '人工复核备注：',
            '',
            r.get('review_note', ''),
            '',
        ])
    return '\n'.join(parts)
