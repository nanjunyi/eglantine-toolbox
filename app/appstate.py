"""全局应用状态：安装目录、本地版本、汉化状态、可选版本列表。

页面不再各自去读 exe / 读配置，而是订阅 ``changed`` 信号后统一刷新，
避免「A 页改了目录，B 页按钮还亮着」这种状态漂移。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .core import buildinfo, config, installer
from .core import release as rel


class AppState(QObject):
    changed = Signal()
    releases_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.cfg: dict = config.load_config()
        self.install_dir: Path | None = None
        self.info: buildinfo.BuildInfo | None = None
        self.status: dict = {"exists": False, "patched": False, "zh_pack": False}
        self.releases: list[rel.Release] = []
        self.target: rel.Release | None = None

    # ------------------------------------------------------------------ 配置
    def save(self) -> None:
        config.save_config(self.cfg)

    def get(self, key: str, default=None):
        return self.cfg.get(key, default)

    def set(self, key: str, value) -> None:
        if self.cfg.get(key) != value:
            self.cfg[key] = value
            self.save()

    # ------------------------------------------------------------------ 目录
    @property
    def has_dir(self) -> bool:
        return bool(self.install_dir and self.install_dir.is_dir())

    @property
    def installed(self) -> bool:
        return bool(self.install_dir and (self.install_dir / installer.EXE).exists())

    @property
    def exe(self) -> Path:
        assert self.install_dir is not None
        return self.install_dir / installer.EXE

    def set_dir(self, path: Path, log=None) -> None:
        self.install_dir = Path(path)
        self.cfg["install_dir"] = str(self.install_dir)
        self.save()
        if log:
            log(f"安装位置:{self.install_dir}")
        self.refresh()

    # ------------------------------------------------------------------ 刷新
    def refresh(self) -> None:
        self.info = None
        if self.installed:
            try:
                self.info = buildinfo.read_build_info(self.exe)
            except Exception:
                self.info = None
            try:
                self.status = installer.install_state(self.install_dir)
            except Exception:
                self.status = {"exists": True, "patched": False, "zh_pack": False}
        else:
            self.status = {
                "exists": False,
                "patched": False,
                "zh_pack": False,
                "language": installer.current_language(),
                "localized": False,
            }
        self.changed.emit()

    # ------------------------------------------------------------------ 版本
    def set_releases(self, items: list[rel.Release]) -> None:
        self.releases = items
        wanted = self.cfg.get("selected_tag", "")
        chosen = None
        for item in items:
            if item.tag == wanted:
                chosen = item
                break
        self.target = chosen or (items[0] if items else None)
        if self.target is not None:
            self.cfg["selected_tag"] = self.target.tag
            self.save()
        self.releases_changed.emit()
        self.changed.emit()

    def select(self, tag: str) -> None:
        for item in self.releases:
            if item.tag == tag:
                self.target = item
                self.cfg["selected_tag"] = tag
                self.save()
                self.changed.emit()
                return

    # ------------------------------------------------------------------ 判定
    def same_as_local(self) -> bool:
        if not self.installed or self.info is None or self.target is None:
            return False
        return rel.same_release(self.info.tag, self.target)

    def badge(self) -> tuple[str, str]:
        """(文本, 颜色类型) —— 页面直接交给 Badge。"""
        if not self.installed:
            return "● 未安装", "muted"
        st = self.status
        if st.get("localized"):
            return "● 已汉化", "ok"
        if st.get("patched") or st.get("zh_pack"):
            return "● 未汉化", "warn"
        return "● 官方原版", "muted"
