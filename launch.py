"""Start the independent development copy on localhost only."""
import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parent
local_packages = root / '.packages'
if local_packages.exists():
    sys.path.insert(0, str(local_packages))
os.environ.setdefault('STREAMLIT_BROWSER_GATHER_USAGE_STATS', 'false')
try:
    from streamlit.web import cli
except ImportError:
    raise SystemExit('请先安装 requirements.txt 中的依赖。')
sys.argv = ['streamlit', 'run', str(root / 'app.py'), '--global.developmentMode=false',
            '--server.address=127.0.0.1', '--server.port=8501', '--browser.serverPort=8501',
            '--server.headless=true', '--browser.gatherUsageStats=false', '--logger.level=warning']
sys.exit(cli.main())
