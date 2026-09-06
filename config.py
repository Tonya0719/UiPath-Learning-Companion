"""Local configuration; no shell expansion of .env values."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / '.env').exists():
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('\"\''))
MOCK_LLM = os.getenv('MOCK_LLM', 'true').lower() == 'true'
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4.1-mini')
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.0'))
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '45'))
DATA_DIR = ROOT / 'data'
