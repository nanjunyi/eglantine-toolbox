"""公共工具：进度回调协议、取消信号、哈希、体积格式化。"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

#: 资源目录（源码运行 = app/resources，打包后 = _MEIPASS/app/resources）
def resource_path(name: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "app" / "resources" / name
    return Path(__file__).resolve().parent.parent / "resources" / name


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """工具自身所在目录（打包后是 exe 所在目录）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


class Cancelled(Exception):
    """用户取消任务。"""


class Progress:
    """任务进度回调的默认实现（命令行/无界面时使用）。"""

    def log(self, message: str) -> None:
        print(message, flush=True)

    def stage(self, message: str) -> None:
        print(f"== {message}", flush=True)

    def progress(self, current: int, total: int, text: str = "") -> None:
        pass

    def cancelled(self) -> bool:
        return False

    def check_cancel(self) -> None:
        if self.cancelled():
            raise Cancelled()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fp:
        for block in iter(lambda: fp.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def human_speed(bytes_per_sec: float) -> str:
    return f"{human_size(bytes_per_sec)}/s"
