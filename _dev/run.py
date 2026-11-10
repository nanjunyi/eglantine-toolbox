"""开发时启动入口：python _dev/run.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import run  # noqa: E402

sys.exit(run())
