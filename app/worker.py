"""后台任务线程：进度、日志、取消。"""

from __future__ import annotations

import threading
import traceback

from PySide6.QtCore import QThread, Signal

from .core.common import Cancelled


class Job(QThread):
    """在线程里跑一个函数；函数收到 self 作为 progress 对象。"""

    log_signal = Signal(str)
    stage_signal = Signal(str)
    progress_signal = Signal(int, int, str)
    done_signal = Signal(object)
    failed_signal = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._cancel = threading.Event()

    # ---- Progress 协议（由核心代码调用） ----
    def log(self, message: str) -> None:
        self.log_signal.emit(str(message))

    def stage(self, message: str) -> None:
        self.stage_signal.emit(str(message))

    def progress(self, current: int, total: int, text: str = "") -> None:
        self.progress_signal.emit(int(current), int(total), str(text))

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check_cancel(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    # ---- 控制 ----
    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:  # noqa: D102
        try:
            result = self._fn(self)
        except Cancelled:
            self.failed_signal.emit("__cancelled__")
        except Exception as exc:  # noqa: BLE001
            detail = traceback.format_exc(limit=6)
            self.log_signal.emit(detail)
            self.failed_signal.emit(str(exc) or exc.__class__.__name__)
        else:
            self.done_signal.emit(result)
