"""Eglantine 工具箱 —— 主窗口（侧边栏 + 页面容器 + 状态栏 + 日志抽屉）。"""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__, theme
from .appstate import AppState
from .constants import APP_ID, APP_NAME, DISPLAY_NAME
from .core import buildinfo, config, installer, release
from .core.common import app_dir
from .dialogs import error
from .icon import app_icon
from .pages.base import Page
from .pages.cheats_page import CheatsPage
from .pages.launch_page import LaunchPage
from .pages.saves_page import SavesPage
from .pages.settings_page import SettingsPage
from .pages.update_page import UpdatePage
from .sidebar import Sidebar
from .taskbus import TaskBus
from .widgets import LogView

LOG_HEIGHT = 150
LOG_HEIGHT_COLLAPSED = 34


class LogDrawer(QFrame):
    """底部日志抽屉：可折叠，跨页面共享。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Drawer")
        col = QVBoxLayout(self)
        col.setContentsMargins(14, 4, 14, 8)
        col.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.toggle = QPushButton("▾ 日志")
        self.toggle.setObjectName("Ghost")
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.clicked.connect(self.toggle_collapsed)
        btn_copy = QPushButton("复制")
        btn_copy.setObjectName("Ghost")
        btn_copy.clicked.connect(self.copy_all)
        btn_clear = QPushButton("清空")
        btn_clear.setObjectName("Ghost")
        btn_clear.clicked.connect(self.clear)
        head.addWidget(self.toggle)
        head.addStretch(1)
        head.addWidget(btn_copy)
        head.addWidget(btn_clear)
        col.addLayout(head)

        self.view = LogView()
        self.view.setMinimumHeight(60)
        col.addWidget(self.view, 1)
        self.collapsed = False

    def append(self, text: str) -> None:
        self.view.append_line(text)

    def clear(self) -> None:
        self.view.clear()

    def copy_all(self) -> None:
        QApplication.clipboard().setText(self.view.toPlainText())

    def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        self.view.setVisible(not self.collapsed)
        self.toggle.setText("▸ 日志" if self.collapsed else "▾ 日志")
        self.setFixedHeight(LOG_HEIGHT_COLLAPSED if self.collapsed else LOG_HEIGHT)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = AppState()
        self.bus = TaskBus(self)
        self.pages: dict[str, Page] = {}
        self.current: Page | None = None
        self._log_file = config.log_dir() / f"tool-{datetime.date.today():%Y%m%d}.log"

        release.set_net(
            self.state.get("use_system_proxy", True),
            self.state.get("mirror", ""),
        )

        self.setWindowTitle(DISPLAY_NAME)
        self.setWindowIcon(app_icon())
        self._restore_geometry()

        self._build_ui()
        self._wire_bus()
        QTimer.singleShot(60, self._bootstrap)

    # ------------------------------------------------------------------ 布局
    def _restore_geometry(self) -> None:
        cfg = self.state.cfg
        if int(cfg.get("ui_version", 1)) < 2:
            # 旧版窗口偏窄，加侧边栏后会挤，直接改用新默认值
            width, height = 1200, 800
        else:
            width = int(cfg.get("width", 1200))
            height = int(cfg.get("height", 800))
        # 别超出屏幕（1440×900 这类小屏很常见）
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            width = max(1060, min(width, avail.width() - 40))
            height = max(700, min(height, avail.height() - 40))
        self.resize(width, height)
        self.setMinimumSize(min(1060, width), min(700, height))

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = Sidebar(f"v{__version__}")
        self.sidebar.selected.connect(self._on_nav)
        row.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        right.addWidget(self._build_status_bar())
        self.drawer = LogDrawer()
        self.drawer.setFixedHeight(LOG_HEIGHT)
        right.addWidget(self.drawer)

        row.addLayout(right, 1)

        self._add_page(LaunchPage(self))
        self._add_page(SavesPage(self))
        self._add_page(CheatsPage(self))
        self._add_page(UpdatePage(self))
        self._add_page(SettingsPage(self))

        self.sidebar.set_current(0)
        self._on_nav(0)

    def _add_page(self, page: Page) -> None:
        self.pages[page.key] = page
        self.stack.addWidget(page)

    def _build_status_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(40)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(10)
        self.status = QLabel("就绪")
        self.status.setObjectName("Subtitle")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(220)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("Ghost")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.bus.cancel)
        lay.addWidget(self.status, 1)
        lay.addWidget(self.progress)
        lay.addWidget(self.btn_cancel)
        return bar

    # ------------------------------------------------------------------ 信号
    def _wire_bus(self) -> None:
        self.bus.log_signal.connect(self.log)
        self.bus.stage_changed.connect(self._on_stage)
        self.bus.progress_changed.connect(self._on_progress)
        self.bus.busy_changed.connect(self._on_busy)
        self.bus.finished.connect(self._on_finished)
        self.bus.failed.connect(self._on_failed)
        self.state.changed.connect(self._broadcast_state)

    def _on_nav(self, index: int) -> None:
        keys = [b.key for b in self.sidebar.buttons]
        if not (0 <= index < len(keys)):
            return
        page = self.pages.get(keys[index])
        if page is None:
            return
        self.current = page
        self.stack.setCurrentWidget(page)
        page.on_show()

    def _broadcast_state(self) -> None:
        for page in self.pages.values():
            try:
                page.apply_state()
            except Exception as exc:  # noqa: BLE001
                self.log(f"页面刷新失败（{page.key}）：{exc}")

    def _on_busy(self, busy: bool) -> None:
        self.btn_cancel.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status.setText("就绪")
        for page in self.pages.values():
            page.apply_busy(busy)

    def _on_stage(self, text: str) -> None:
        self.status.setText(text)
        self.log(f"—— {text} ——")

    def _on_progress(self, current: int, total: int, text: str) -> None:
        if total > 0:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(current * 1000 / total))
        if text:
            self.status.setText(text)

    def _on_finished(self, label: str, ok: bool) -> None:
        if not ok:
            self.status.setText(f"{label}未完成")

    def _on_failed(self, label: str, message: str) -> None:
        if message == "__cancelled__":
            self.status.setText("已取消")
            self.log("任务已取消")
            return
        self.status.setText(f"{label}失败")
        error(self, f"{label}失败", message)

    # ------------------------------------------------------------------ 启动
    def _bootstrap(self) -> None:
        self.log(f"{DISPLAY_NAME} {__version__} 启动")
        candidate = self.state.get("install_dir")
        if candidate and Path(candidate).is_dir():
            self.state.set_dir(Path(candidate), log=False)
        else:
            found = buildinfo.find_install_dir(app_dir())
            if found:
                self.state.set_dir(found, log=False)
            elif self._can_use_app_dir():
                self.state.set_dir(app_dir(), log=False)
                self.log("没找到 eglantine.exe，将把工具所在目录作为安装位置（可全新安装）")
            else:
                self.log("请到「更新与汉化」页点「浏览…」选择目录（空目录会自动全新安装）")
                self.state.refresh()
        page = self.pages.get("update")
        if page is not None:
            QTimer.singleShot(400, lambda: page.check_updates(silent=True))

    @staticmethod
    def _can_use_app_dir() -> bool:
        base = app_dir()
        if (base / installer.UPDATE_DIR / "pkg.zip").exists():
            return True
        try:
            return os.access(base, os.W_OK)
        except Exception:
            return False

    # ------------------------------------------------------------------ 公共
    def log(self, text: str) -> None:
        self.drawer.append(text)
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            with self._log_file.open("a", encoding="utf-8") as fp:
                fp.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")
        except Exception:
            pass

    @property
    def log_file(self) -> Path:
        return self._log_file

    def open_path(self, path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @staticmethod
    def app_dir() -> Path:
        return app_dir()

    def goto(self, key: str) -> None:
        for i, btn in enumerate(self.sidebar.buttons):
            if btn.key == key:
                self.sidebar.set_current(i)
                return

    def launch_emulator(self, rom=None) -> bool:
        if not self.state.installed:
            error(self, "还没安装", "目录里还没有 eglantine.exe，请先到「更新与汉化」页安装。")
            return False
        if installer.emulator_running():
            self.log("模拟器已经在运行了")
            return False
        try:
            installer.launch_emulator(self.state.install_dir, rom=rom)
            self.log(f"已启动模拟器{('：' + rom.name) if rom else ''}")
            return True
        except Exception as exc:  # noqa: BLE001
            error(self, "启动失败", str(exc))
            return False

    # ------------------------------------------------------------------ 关闭
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not getattr(self, "_titlebar_done", False):
            self._titlebar_done = True
            apply_dark_titlebar(self)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.bus.busy():
            if not (
                QMessageBox.question(
                    self,
                    "任务进行中",
                    "还有任务在运行，退出会中断它。确定退出吗？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                == QMessageBox.Yes
            ):
                event.ignore()
                return
            self.bus.wait(3000)
        self.state.cfg["width"] = self.width()
        self.state.cfg["height"] = self.height()
        self.state.cfg["ui_version"] = 2
        self.state.save()
        event.accept()


def apply_dark_titlebar(window: QWidget) -> bool:
    """Windows 10/11 的标题栏跟随暗色（否则顶部一条白杠很割裂）。

    走 DWM：先开 immersive dark mode，再（Win11）把标题栏/边框染成窗口底色。
    任何一步失败都静默跳过，不影响使用。
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi

        def set_attr(attr: int, value: int) -> None:
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(data), ctypes.sizeof(data))

        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE（旧版系统是 19）
        set_attr(20, 1)
        set_attr(19, 1)
        # 35 = DWMWA_CAPTION_COLOR, 34 = DWMWA_BORDER_COLOR（Win11 才支持，失败无妨）
        caption = 0x001A1614  # COLORREF(0x00BBGGRR) ← #14161a
        set_attr(35, caption)
        set_attr(34, 0x002B2F39)
        return True
    except Exception:
        return False


def run() -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(APP_ID)
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(theme.stylesheet())
    app.setWindowIcon(app_icon())

    from PySide6.QtCore import QLockFile

    lock = QLockFile(str(config.config_dir() / "tool.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(200):
        QMessageBox.information(None, "已在运行", "工具箱已经在运行了，请在任务栏切换过去。")
        return 0

    window = MainWindow()
    window.show()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(run())
