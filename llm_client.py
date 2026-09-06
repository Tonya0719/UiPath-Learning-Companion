import json
import re
import socket
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from pydantic import ValidationError
import config
from runtime import variant, record
from prompts.templates import system_prompt, prompt_version

class ModelError(RuntimeError):
    pass


def source_ids_in_prose(result, cards):
    """Return supplied card IDs leaked outside fields reserved for citations."""
    data = result.model_dump()
    for field in ('evidence', 'course_evidence_ids', 'reference_question_ids'):
        data.pop(field, None)
    prose = json.dumps(data, ensure_ascii=False)
    return sorted({card['id'] for card in cards if card.get('id') and card['id'] in prose})

def unsupported_learning_claims(result, cards):
    """Flag common AI comparison claims when the supplied cards do not state them."""
    if not hasattr(result, 'answer'):
        return []
    prose = ' '.join(str(value or '') for value in (
        result.answer, getattr(result, 'common_misunderstanding', None),
        getattr(result, 'exercise_connection', None)))
    evidence = json.dumps(cards, ensure_ascii=False)
    checks = {
        'unstructured data/content': r'unstructured\s+(?:data|content)',
        'AI judgment': r'\b(?:make|makes|making|require|requires|requiring)\s+(?:human\s+)?judg(?:e)?ment',
    }
    return [label for label, pattern in checks.items()
            if re.search(pattern, prose, re.I) and not re.search(pattern, evidence, re.I)]

def remove_unsupported_learning_claims(result):
    """Apply a narrow evidence-backed fallback after repeated semantic retries."""
    safe = ('AI, in contrast, is represented in the course through machine learning, '
            'while agentic automation can plan and adapt.')
    for field in ('answer', 'common_misunderstanding', 'exercise_connection'):
        value = getattr(result, field, None)
        if not value:
            continue
        sentences = re.split(r'(?<=[.!?])\s+', value)
        cleaned = [safe if re.search(r'unstructured\s+(?:data|content)|\bmake\s+(?:human\s+)?judg(?:e)?ments?', sentence, re.I)
                   else sentence for sentence in sentences]
        setattr(result, field, ' '.join(dict.fromkeys(cleaned)))
    return result

def thinking_options(task):
    """Apply only to the official DeepSeek V4 endpoint; preserve other tasks/providers."""
    if urlparse(config.LLM_BASE_URL).hostname != 'api.deepseek.com' or not config.LLM_MODEL.startswith('deepseek-v4-'):
        return {}
    if task == 'learning':
        return {'thinking': {'type': 'disabled'}}
    if task in {'generate', 'debug'}:
        return {'thinking': {'type': 'enabled'}, 'reasoning_effort': 'low'}
    return {}


def _request(messages, task=None):
    if not config.LLM_API_KEY:
        raise ModelError('尚未配置 API key。请在开发副本的 .env 中配置，勿发送到群聊或写入代码。')
    payload = {'model': config.LLM_MODEL, 'temperature': config.LLM_TEMPERATURE,
               'messages': messages, 'response_format': {'type': 'json_object'}}
    payload.update(thinking_options(task))
    req = Request(config.LLM_BASE_URL + '/chat/completions',
                  data=json.dumps(payload).encode('utf-8'), method='POST',
                  headers={'Authorization': 'Bearer ' + config.LLM_API_KEY, 'Content-Type': 'application/json'})
    for attempt in range(2):
        try:
            with urlopen(req, timeout=config.LLM_TIMEOUT) as response:
                body = json.load(response)
            return body['choices'][0]['message']['content']
        except HTTPError as exc:
            if attempt == 0 and exc.code in {429, 500, 502, 503, 504}:
                record('transport_retry', http_status=exc.code)
                time.sleep(1)
                continue
            raise ModelError(f'模型接口返回 HTTP {exc.code}；请检查配置或稍后重试。') from None
        except (URLError, TimeoutError, socket.timeout):
            raise ModelError('模型连接失败或超时，请检查网络和接口地址。') from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ModelError('模型接口返回了无法识别的响应。') from None

def call_model(task, inputs, cards, schema, demo, references=None):
    mode = variant.get()
    system = system_prompt(task, mode)
    system += '\nOUTPUT_SCHEMA:\n' + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    payload = {'mode': mode, 'inputs': inputs}
    if mode == 'C':
        payload.update(EVIDENCE=cards, STYLE_REFERENCES=references or [])
    user = json.dumps(payload, ensure_ascii=False)
    record('model_request', mock=config.MOCK_LLM, model=config.LLM_MODEL,
           temperature=config.LLM_TEMPERATURE, thinking_options=thinking_options(task),
           prompt_version=prompt_version(mode), system=system, user=user)
    if config.MOCK_LLM:
        return schema.model_validate(demo)
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
    # Structural/format errors get one repair. A narrowly detected semantic
    # evidence violation may use a second repair before the safe fallback.
    for attempt in range(3):
        raw = _request(messages, task=task)
        record('model_response', raw=raw, attempt=attempt + 1)
        record('validation_started', attempt=attempt + 1)
        try:
            result = schema.model_validate_json(raw)
            if mode == 'C' and source_ids_in_prose(result, cards):
                raise ValueError('source ID outside citation fields')
            if mode == 'C' and task == 'learning' and unsupported_learning_claims(result, cards):
                raise ValueError('unsupported AI comparison claim')
            return result
        except (ValidationError, ValueError, TypeError) as exc:
            semantic_retry = str(exc) == 'unsupported AI comparison claim'
            if semantic_retry and attempt >= 2:
                repaired = remove_unsupported_learning_claims(result)
                if not unsupported_learning_claims(repaired, cards):
                    record('semantic_fallback', issue='unsupported AI comparison claim')
                    return repaired
            if (semantic_retry and attempt >= 2) or (not semantic_retry and attempt >= 1):
                raise ModelError('模型回复未通过格式检查，已尝试修复一次。请重试或调整问题。') from None
            record('semantic_retry' if semantic_retry else 'format_retry', attempt=attempt + 1)
            messages.append({'role': 'assistant', 'content': raw if isinstance(raw, str) else ''})
            if str(exc) == 'source ID outside citation fields':
                correction = (' Source IDs must appear only in evidence, course_evidence_ids, or '
                              'reference_question_ids, never in user-facing prose.')
            elif str(exc) == 'unsupported AI comparison claim':
                correction = (' Remove claims that AI handles unstructured data/content or makes '
                              'judgments unless those exact ideas are stated in EVIDENCE.')
            else:
                correction = ''
            messages.append({'role': 'user', 'content': 'The response failed validation. Return one valid JSON object matching OUTPUT_SCHEMA. Use a non-answer status if necessary; do not invent content.' + correction})
