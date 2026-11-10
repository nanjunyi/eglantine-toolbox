"""打包入口（PyInstaller 用）：python 无参数启动图形界面。"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    try:
        from app.main import run

        return run()
    except Exception:
        detail = traceback.format_exc()
        try:
            from app.core.config import log_dir

            with (log_dir() / "crash.log").open("a", encoding="utf-8") as fp:
                fp.write(detail + "\n")
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "启动失败", f"程序启动时出错：\n\n{detail[-1200:]}")
        except Exception:
            print(detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
