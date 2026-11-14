"""主题样式表：白天 / 夜间两套调色板，同一份 QSS 模板。

颜色全部走 Palette 的 token（历史上散在 QSS 里的 42 处十六进制字面量已收编），
切换主题时只需要换一个 Palette 重新格式化模板，选择器一行都不用动。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MODES = ("system", "dark", "light")
MODE_LABELS = {"system": "跟随系统", "dark": "夜间", "light": "白天"}


@dataclass(frozen=True)
class Palette:
    name: str
    is_dark: bool
    # 背景 / 表面
    BG: str
    CARD: str
    CARD_HOVER: str
    SUNKEN: str  # 侧边栏、状态栏、日志抽屉
    INPUT_BG: str
    PROGRESS_TRACK: str
    TOOLTIP_BG: str
    # 描边
    BORDER: str
    BORDER_STRONG: str
    INPUT_BORDER: str
    PROGRESS_BORDER: str
    CHECK_BORDER: str
    TOOLTIP_BORDER: str
    SCROLL_HANDLE: str
    SCROLL_HANDLE_HOVER: str
    # 按钮
    BTN_BG: str
    BTN_BORDER: str
    BTN_HOVER_BG: str
    BTN_PRESSED_BG: str
    DISABLED_TEXT: str
    DISABLED_BG: str
    DISABLED_BORDER: str
    PRIMARY_TEXT: str
    PRIMARY_DISABLED_BG: str
    PRIMARY_DISABLED_TEXT: str
    # 文字
    TEXT: str
    MUTED: str
    LOG_TEXT: str
    SELECTION_BG: str
    COMBO_SELECTED: str
    # 主色 / 状态色
    ACCENT: str
    ACCENT_HOVER: str
    GREEN: str
    AMBER: str
    RED: str


DARK = Palette(
    name="dark",
    is_dark=True,
    BG="#14161a",
    CARD="#1b1e24",
    CARD_HOVER="#20242b",
    SUNKEN="#101216",
    INPUT_BG="#111318",
    PROGRESS_TRACK="#0d0f13",
    TOOLTIP_BG="#22262e",
    BORDER="#2b2f39",
    BORDER_STRONG="#3d4556",
    INPUT_BORDER="#2b2f39",
    PROGRESS_BORDER="#232731",
    CHECK_BORDER="#3a4152",
    TOOLTIP_BORDER="#3a4050",
    SCROLL_HANDLE="#3a4050",
    SCROLL_HANDLE_HOVER="#4a5164",
    BTN_BG="#252a34",
    BTN_BORDER="#333947",
    BTN_HOVER_BG="#2d323e",
    BTN_PRESSED_BG="#22262e",
    DISABLED_TEXT="#6a7284",
    DISABLED_BG="#1e2229",
    DISABLED_BORDER="#2a2f39",
    PRIMARY_TEXT="#ffffff",
    PRIMARY_DISABLED_BG="#333a52",
    PRIMARY_DISABLED_TEXT="#8b93aa",
    TEXT="#e7eaf1",
    MUTED="#98a0b3",
    LOG_TEXT="#c9d1e0",
    SELECTION_BG="#35406a",
    COMBO_SELECTED="#2a3556",
    ACCENT="#5b7cfa",
    ACCENT_HOVER="#6f8dfd",
    GREEN="#3ddc97",
    AMBER="#f0b429",
    RED="#ff6b6b",
)

LIGHT = Palette(
    name="light",
    is_dark=False,
    BG="#f5f6f8",
    CARD="#ffffff",
    CARD_HOVER="#eef1f6",
    SUNKEN="#eceef2",
    INPUT_BG="#ffffff",
    PROGRESS_TRACK="#e9ecf1",
    TOOLTIP_BG="#ffffff",
    BORDER="#dcdfe6",
    BORDER_STRONG="#c6cad3",
    INPUT_BORDER="#d4d7de",
    PROGRESS_BORDER="#dfe2e8",
    CHECK_BORDER="#c2c7d1",
    TOOLTIP_BORDER="#dcdfe6",
    SCROLL_HANDLE="#c6cad3",
    SCROLL_HANDLE_HOVER="#a9b0bd",
    BTN_BG="#ffffff",
    BTN_BORDER="#d6dae2",
    BTN_HOVER_BG="#f3f5f9",
    BTN_PRESSED_BG="#e9ecf2",
    DISABLED_TEXT="#a9aeb9",
    DISABLED_BG="#f2f3f5",
    DISABLED_BORDER="#e3e5ea",
    PRIMARY_TEXT="#ffffff",
    PRIMARY_DISABLED_BG="#e2e8fb",
    PRIMARY_DISABLED_TEXT="#8a94ad",
    TEXT="#1f2329",
    MUTED="#6b7280",
    LOG_TEXT="#3b4250",
    SELECTION_BG="#d3ddff",
    COMBO_SELECTED="#e2e9ff",
    ACCENT="#5b7cfa",
    ACCENT_HOVER="#4a68e0",
    GREEN="#12996a",
    AMBER="#b3760a",
    RED="#d64545",
)

_MODES = {"dark": DARK, "light": LIGHT}
_MODE = "dark"


def _rgba(color: str, alpha: float) -> str:
    """"#5b7cfa", 0.16 → "rgba(91, 124, 250, 0.16)"（QSS 不认 #RRGGBBAA）。"""
    c = (color or "").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        r = g = b = 0
    return f"rgba({r}, {g}, {b}, {alpha:g})"


def _system_is_light() -> bool:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False
        return app.styleHints().colorScheme() == Qt.ColorScheme.Light
    except Exception:
        return False


def set_mode(mode: str) -> str:
    """记下用户选择（system / dark / light），非法值回落 dark。"""
    global _MODE
    value = (mode or "dark").strip().lower()
    _MODE = value if value in MODES else "dark"
    return _MODE


def mode() -> str:
    return _MODE


def resolve(mode_name: str | None = None) -> Palette:
    target = (mode_name or _MODE or "dark").strip().lower()
    if target == "light":
        return LIGHT
    if target == "system":
        # 系统拿不到（Qt < 6.5 / 无平台插件）时保持暗色，别把老用户晃到白屏
        return LIGHT if _system_is_light() else DARK
    return DARK


def current() -> Palette:
    return resolve(_MODE)


def is_dark() -> bool:
    return current().is_dark


def _template(p: Palette) -> str:
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {p.TEXT};
}}
QMainWindow, #Root {{
    background: {p.BG};
}}
QFrame#Card {{
    background: {p.CARD};
    border: 1px solid {p.BORDER};
    border-radius: 12px;
}}
QLabel#Title {{
    font-size: 19pt;
    font-weight: 600;
    color: {p.TEXT};
}}
QLabel#Subtitle {{
    color: {p.MUTED};
    font-size: 9pt;
}}
QLabel#SectionLabel {{
    color: {p.MUTED};
    font-size: 9pt;
}}
QLabel#Strong {{
    font-size: 12.5pt;
    font-weight: 600;
}}
QLabel#Mono {{
    color: {p.MUTED};
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 9pt;
}}
QLabel#Verdict {{
    font-size: 9.5pt;
    font-weight: 600;
}}
QLabel#Badge {{
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 9pt;
    font-weight: 600;
}}
QPushButton {{
    background: {p.BTN_BG};
    border: 1px solid {p.BTN_BORDER};
    border-radius: 8px;
    padding: 9px 16px;
    color: {p.TEXT};
}}
QPushButton:hover {{
    background: {p.BTN_HOVER_BG};
    border-color: {p.BORDER_STRONG};
}}
QPushButton:pressed {{
    background: {p.BTN_PRESSED_BG};
}}
QPushButton:disabled {{
    color: {p.DISABLED_TEXT};
    background: {p.DISABLED_BG};
    border-color: {p.DISABLED_BORDER};
}}
QPushButton#Primary {{
    background: {p.ACCENT};
    border: 1px solid {p.ACCENT};
    color: {p.PRIMARY_TEXT};
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background: {p.ACCENT_HOVER};
    border-color: {p.ACCENT_HOVER};
}}
QPushButton#Primary:disabled {{
    background: {p.PRIMARY_DISABLED_BG};
    border-color: {p.PRIMARY_DISABLED_BG};
    color: {p.PRIMARY_DISABLED_TEXT};
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {p.BORDER};
    color: {p.MUTED};
    padding: 6px 12px;
}}
QPushButton#Ghost:hover {{
    color: {p.TEXT};
    border-color: {p.BORDER_STRONG};
}}
QComboBox {{
    background: {p.INPUT_BG};
    border: 1px solid {p.INPUT_BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    color: {p.TEXT};
}}
QComboBox:hover {{
    border-color: {p.BORDER_STRONG};
}}
QComboBox:focus {{
    border-color: {p.ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {p.CARD};
    border: 1px solid {p.BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {p.COMBO_SELECTED};
    outline: none;
}}
QLineEdit {{
    background: {p.INPUT_BG};
    border: 1px solid {p.INPUT_BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    color: {p.TEXT};
    selection-background-color: {p.SELECTION_BG};
}}
QLineEdit:focus {{
    border-color: {p.ACCENT};
}}
QCheckBox {{
    color: {p.TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {p.CHECK_BORDER};
    background: {p.INPUT_BG};
}}
QCheckBox::indicator:checked {{
    background: {p.ACCENT};
    border-color: {p.ACCENT};
    image: url("__CHECK__");
}}
QPlainTextEdit {{
    background: {p.INPUT_BG};
    border: 1px solid {p.BORDER};
    border-radius: 8px;
    padding: 8px;
    color: {p.LOG_TEXT};
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 9pt;
    selection-background-color: {p.SELECTION_BG};
}}
QProgressBar {{
    background: {p.PROGRESS_TRACK};
    border: 1px solid {p.PROGRESS_BORDER};
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {p.ACCENT};
    border-radius: 5px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {p.SCROLL_HANDLE};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p.SCROLL_HANDLE_HOVER};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QToolTip {{
    background: {p.TOOLTIP_BG};
    color: {p.TEXT};
    border: 1px solid {p.TOOLTIP_BORDER};
    padding: 5px 8px;
}}
QMessageBox {{
    background: {p.BG};
}}
QDialog {{
    background: {p.BG};
}}

/* ---------------------------------------------------------------- 侧边栏 */
QFrame#Sidebar {{
    background: {p.SUNKEN};
    border-right: 1px solid {p.BORDER};
}}
QLabel#SidebarBrand {{
    font-size: 13pt;
    font-weight: 600;
    color: {p.TEXT};
}}
QLabel#SidebarVersion {{
    color: {p.MUTED};
    font-size: 8.5pt;
}}
QScrollArea#SidebarScroll, #SidebarHolder {{
    background: transparent;
    border: none;
}}
QToolButton#Nav {{
    text-align: left;
    padding: 8px 10px;
    border: none;
    border-radius: 8px;
    color: {p.MUTED};
    background: transparent;
    font-size: 10pt;
}}
QToolButton#Nav:hover {{
    background: {p.CARD_HOVER};
    color: {p.TEXT};
}}
QToolButton#Nav:checked {{
    background: {_rgba(p.ACCENT, 0.16)};
    color: {p.TEXT};
    font-weight: 600;
}}

/* ---------------------------------------------------------------- 页面 */
QLabel#PageTitle {{
    font-size: 16pt;
    font-weight: 600;
    color: {p.TEXT};
}}
QLabel#PageDesc {{
    color: {p.MUTED};
    font-size: 9pt;
}}
QLabel#Hint {{
    color: {p.MUTED};
    font-size: 9pt;
}}
QLabel#Empty {{
    color: {p.MUTED};
    font-size: 10pt;
    padding: 24px;
}}
QFrame#StatusBar {{
    background: {p.SUNKEN};
    border-top: 1px solid {p.BORDER};
}}
QFrame#Drawer {{
    background: {p.SUNKEN};
    border-top: 1px solid {p.BORDER};
}}
QLabel#DrawerTitle {{
    color: {p.MUTED};
    font-size: 9pt;
}}
QPushButton#Danger {{
    background: transparent;
    border: 1px solid {_rgba(p.RED, 0.5)};
    color: {p.RED};
    padding: 6px 12px;
    border-radius: 8px;
}}
QPushButton#Danger:hover {{
    background: {_rgba(p.RED, 0.12)};
}}
QPushButton#Danger:disabled {{
    color: {p.DISABLED_TEXT};
    border-color: {p.DISABLED_BORDER};
    background: {p.DISABLED_BG};
}}
QScrollArea#PageScroll {{
    background: transparent;
    border: none;
}}
QScrollArea#PageScroll > QWidget > QWidget {{
    background: transparent;
}}
QListWidget {{
    background: {p.CARD};
    border: 1px solid {p.BORDER};
    border-radius: 10px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 0px;
    margin: 2px 0;
    border-radius: 8px;
    color: {p.TEXT};
}}
QListWidget::item:hover {{
    background: {p.CARD_HOVER};
}}
QListWidget::item:selected {{
    background: {_rgba(p.ACCENT, 0.20)};
    color: {p.TEXT};
}}
QMenu {{
    background: {p.CARD};
    border: 1px solid {p.BORDER};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: 6px;
    color: {p.TEXT};
    background: transparent;
}}
QMenu::item:selected {{
    background: {_rgba(p.ACCENT, 0.22)};
    color: {p.TEXT};
}}
QMenu::item:disabled {{
    color: {p.MUTED};
}}
QMenu::separator {{
    height: 1px;
    background: {p.BORDER};
    margin: 5px 8px;
}}
"""


def _check_icon() -> str:
    """生成勾选图标（QSS 无法直接画对勾）。"""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygon

    from .core.config import config_dir

    target = config_dir() / "ui" / "check.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        size = 16
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#ffffff"))
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(
            QPolygon(
                [
                    QPoint(4, 8),
                    QPoint(7, 11),
                    QPoint(12, 5),
                ]
            )
        )
        painter.end()
        pm.save(str(target), "PNG")
    return target.as_posix()


def stylesheet(palette: Palette | None = None) -> str:
    p = palette or current()
    try:
        icon = _check_icon()
    except Exception:
        icon = ""
    qss = _template(p).replace("__CHECK__", icon)
    if not icon:
        qss = qss.replace('    image: url("");', "")
    return qss


# 旧代码里直接写 theme.TEXT / theme.MUTED 的地方不少，这里做动态转发，
# 让它们跟随当前主题，而不是停在 import 时的那一份快照。
_LEGACY = {"BG", "CARD", "CARD_HOVER", "BORDER", "TEXT", "MUTED",
           "ACCENT", "ACCENT_HOVER", "GREEN", "AMBER", "RED"}


def __getattr__(name: str):
    if name in _LEGACY:
        return getattr(current(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
