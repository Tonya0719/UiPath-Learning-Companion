"""Local configuration; no shell expansion of .env values."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def _load_streamlit_secrets():
    try:
        import streamlit as st
    except ImportError:
        return {}
    return st.secrets

_secrets = _load_streamlit_secrets()

if (ROOT / '.env').exists():
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('\"\'')) 

def _get(key, default):
    value = os.getenv(key)
    if value not in (None, ''):
        return value
    try:
        return _secrets.get(key, default)
    except Exception:
        return default

MOCK_LLM = str(_get('MOCK_LLM', 'true')).lower() == 'true'
LLM_API_KEY = _get('LLM_API_KEY', '')
LLM_BASE_URL = str(_get('LLM_BASE_URL', 'https://api.openai.com/v1')).rstrip('/')
LLM_MODEL = _get('LLM_MODEL', 'gpt-4.1-mini')
LLM_TEMPERATURE = float(_get('LLM_TEMPERATURE', '0.0'))
LLM_TIMEOUT = int(_get('LLM_TIMEOUT', '45'))
DATA_DIR = ROOT / 'data'
