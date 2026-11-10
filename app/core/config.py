"""工具自身配置、日志与常见目录定位。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..constants import APP_ID, APP_NAME, LEGACY_APP_ID, LEGACY_APP_NAME
from .common import app_dir

# 兼容旧引用（早期代码里有 `config.APP_NAME`）
__all__ = [
    "APP_NAME",
    "APP_ID",
    "config_dir",
    "config_path",
    "load_config",
    "save_config",
    "log_dir",
    "eden_dirs",
    "qt_config_ini",
]


def config_dir() -> Path:
    """非便携场景的配置目录（exe 同级不可写时用）。"""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    path = Path(base) / APP_ID if base else Path.home() / ".eglantine_toolbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def legacy_config_dir() -> Path:
    """2.0.x 及更早版本的兜底目录。只算路径，不创建。"""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return Path(base) / LEGACY_APP_ID if base else Path.home() / ".eglantine_zhcn"


def config_path() -> Path:
    """优先便携（工具同目录），不可写时退到 LOCALAPPDATA。"""
    preferred = app_dir() / f"{APP_NAME}.json"
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        if preferred.exists() or os.access(preferred.parent, os.W_OK):
            return preferred
    except Exception:
        pass
    return config_dir() / "config.json"


def _legacy_paths() -> list[Path]:
    """升级时可读的旧配置位置，按优先级排列。

    三条路径覆盖三种历史场景：
    1. 便携版（exe 同级 `Eglantine汉化工具.json`）
    2. 兜底目录（`%LOCALAPPDATA%\\<新ID>\\config.json`，同名但内容可能是旧的）
    3. 旧兜底目录（`%LOCALAPPDATA%\\EglantineZhCN\\config.json`）
    """
    return [
        app_dir() / f"{LEGACY_APP_NAME}.json",
        config_dir() / "config.json",
        legacy_config_dir() / "config.json",
    ]


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_config() -> dict:
    path = config_path()
    if path.exists():
        data = _read(path)
        if data is not None:
            return data

    # 新版配置不存在（或损坏）→ 找旧位置，命中后立刻落到新路径
    for candidate in _legacy_paths():
        if candidate == path or not candidate.exists():
            continue
        data = _read(candidate)
        if data is None:
            continue
        save_config(data)
        return data
    return {}


def save_config(data: dict) -> None:
    path = config_path()
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def log_dir() -> Path:
    base = app_dir()
    try:
        path = base / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return config_dir()


def eden_dirs() -> list[Path]:
    """模拟器的配置目录（不同分支可能叫 eden / eglantine）。"""
    roaming = os.environ.get("APPDATA")
    local = os.environ.get("LOCALAPPDATA")
    names = ("eden", "eglantine", "Eglantine")
    out: list[Path] = []
    for base in (roaming, local):
        if not base:
            continue
        for name in names:
            out.append(Path(base) / name / "config")
            out.append(Path(base) / name)
    return out


def qt_config_ini() -> Path:
    for d in eden_dirs():
        candidate = d / "qt-config.ini"
        if candidate.exists():
            return candidate
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "eden" / "config" / "qt-config.ini"
