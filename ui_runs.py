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

TASK_LABELS = {'learning': '知识问答', 'next_step': '下一步指导', 'debug': 'Debug', 'generate': '模拟题生成', 'explain': '题目详解'}
STAGES = {'input_validation': '检查输入', 'retrieval_started': '检索相关资料', 'evidence_lookup': '读取题目与步骤证据',
          'retrieval': '已检索资料', 'step_context': '已整理步骤上下文', 'model_request': '等待模型回复',
          'model_response': '已收到模型回复', 'validation_started': '检查输出格式',
          'format_retry': '格式未通过，正在请求修复', 'transport_retry': '接口暂时繁忙，正在重试',
          'result_ready': '已完成结果与引用检查', 'request_failed': '请求失败'}

def clean(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump()
    if isinstance(value, dict):
        return {str(k): '[REDACTED]' if any(word in str(k).lower() for word in ('api_key', 'authorization', 'password', 'secret', 'access_token')) else clean(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, str):
        if config.LLM_API_KEY:
            value = value.replace(config.LLM_API_KEY, '[REDACTED]')
        value = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', value)
        value = re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[REDACTED]', value)
        return value
    return value

def run_test(task, function, inputs, callback=None):
    begin = time.perf_counter()
    result, error = None, None
    with experiment('C') as events, observe(callback):
        record('input_validation')
        try:
            result = function(**inputs)
            record('result_ready')
        except (ModelError, ValidationError, ValueError, OSError) as exc:
            # Never expose raw provider bodies, headers, credentials or tracebacks.
            error = {'type': type(exc).__name__, 'message': '请求未完成，请检查模型配置、网络或数据格式。'}
            record('request_failed', error_type=type(exc).__name__)
    duration = round(time.perf_counter() - begin, 3)
    ids = list(dict.fromkeys(i for e in events if e['kind'] in {'retrieval', 'step_context', 'evidence_lookup'} for i in e.get('ids', [])))
    snapshots = []
    try:
        lookup = {c['id']: c for c in load()}
        snapshots = [evidence_for(lookup[i]).model_dump() for i in ids if i in lookup]
    except (ValueError, OSError):
        pass
    stages = [{k: e[k] for k in ('kind', 'elapsed_seconds', 'attempt', 'http_status') if k in e}
              for e in events if e['kind'] in STAGES]
    for stage in stages:
        stage['label'] = STAGES[stage['kind']]
    row = clean({'run_id': uuid.uuid4().hex[:12], 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'task': task, 'task_label': TASK_LABELS[task], 'variant': 'C', 'mock': config.MOCK_LLM,
        'model': config.LLM_MODEL, 'prompt_version': prompt_version('C'),
        'temperature_requested': config.LLM_TEMPERATURE, 'thinking_options': thinking_options(task),
        'input': inputs, 'output': result.model_dump() if result is not None else None,
        'error': error, 'elapsed_seconds': duration, 'stages': stages, 'retrieved_evidence': snapshots,
        'model_response_count': sum(e['kind'] == 'model_response' for e in events),
        'format_retries': sum(e['kind'] == 'format_retry' for e in events),
        'transport_retries': sum(e['kind'] == 'transport_retry' for e in events),
        'review_status': 'unreviewed', 'review_note': '',
        'notice': '开发功能测试记录，不是正式 A/B/C 评价；演示结果不代表模型效果。'})
    return result, row

def export_json(rows):
    return json.dumps(clean({'format_version': 1, 'runs': rows}), ensure_ascii=False, indent=2)

def export_markdown(rows):
    parts = ['# C 版功能测试记录', '', '开发记录，未进行人工评分。mock=true 表示演示模式，不代表模型效果。',
             '请复核隐私信息后分享；记录包含题目答案。', '']
    for r in clean(rows):
        parts.extend([f"## {r['task_label']} · {r['run_id']}", '',
                      f"时间：{r['created_at_utc']}  ",
                      f"版本：{r['variant']} / {r['prompt_version']} · 模型：{r['model']} · 演示：{r['mock']}  ",
                      f"总耗时：{r['elapsed_seconds']:.2f} 秒 · 格式修复：{r['format_retries']} 次 · 接口重试：{r['transport_retries']} 次", ''])
        for title, obj in [('输入', r['input']), ('回答', r['output']), ('异常', r['error']), ('检索证据', r['retrieved_evidence']), ('处理阶段', r['stages'])]:
            if obj is not None:
                # A dynamic fence prevents user-provided backticks from breaking the export.
                body = json.dumps(obj, ensure_ascii=False, indent=2)
                fence = '`' * max(3, max((len(m.group())+1 for m in re.finditer(r'`+', body)), default=3))
                parts.extend([f'### {title}', '', fence + 'json', body, fence, ''])
        parts.extend(['人工复核备注：', '', r.get('review_note', ''), ''])
    return '\n'.join(parts)
