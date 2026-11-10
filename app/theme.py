"""深色主题样式表。"""

from __future__ import annotations

from pathlib import Path

BG = "#14161a"
CARD = "#1b1e24"
CARD_HOVER = "#20242b"
BORDER = "#2b2f39"
TEXT = "#e7eaf1"
MUTED = "#98a0b3"
ACCENT = "#5b7cfa"
ACCENT_HOVER = "#6f8dfd"
GREEN = "#3ddc97"
AMBER = "#f0b429"
RED = "#ff6b6b"

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, #Root {{
    background: {BG};
}}
QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#Title {{
    font-size: 19pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#Subtitle {{
    color: {MUTED};
    font-size: 9pt;
}}
QLabel#SectionLabel {{
    color: {MUTED};
    font-size: 9pt;
}}
QLabel#Strong {{
    font-size: 12.5pt;
    font-weight: 600;
}}
QLabel#Mono {{
    color: {MUTED};
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
    background: #252a34;
    border: 1px solid #333947;
    border-radius: 8px;
    padding: 9px 16px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: #2d323e;
    border-color: #3d4556;
}}
QPushButton:pressed {{
    background: #22262e;
}}
QPushButton:disabled {{
    color: #6a7284;
    background: #1e2229;
    border-color: #2a2f39;
}}
QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton#Primary:disabled {{
    background: #333a52;
    border-color: #333a52;
    color: #8b93aa;
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {MUTED};
    padding: 6px 12px;
}}
QPushButton#Ghost:hover {{
    color: {TEXT};
    border-color: #3d4556;
}}
QComboBox {{
    background: #111318;
    border: 1px solid #2b2f39;
    border-radius: 8px;
    padding: 7px 12px;
    color: {TEXT};
}}
QComboBox:hover {{
    border-color: #3d4556;
}}
QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: #1b1e24;
    border: 1px solid #2b2f39;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #2a3556;
    outline: none;
}}
QLineEdit {{
    background: #111318;
    border: 1px solid #2b2f39;
    border-radius: 8px;
    padding: 8px 12px;
    color: {TEXT};
    selection-background-color: #35406a;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3a4152;
    background: #111318;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url("__CHECK__");
}}
QPlainTextEdit {{
    background: #111318;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    color: #c9d1e0;
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 9pt;
    selection-background-color: #35406a;
}}
QProgressBar {{
    background: #0d0f13;
    border: 1px solid #232731;
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 5px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: #3a4050;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #4a5164;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QToolTip {{
    background: #22262e;
    color: {TEXT};
    border: 1px solid #3a4050;
    padding: 5px 8px;
}}
QMessageBox {{
    background: {BG};
}}
QDialog {{
    background: {BG};
}}

/* ---------------------------------------------------------------- 侧边栏 */
QFrame#Sidebar {{
    background: #101216;
    border-right: 1px solid {BORDER};
}}
QLabel#SidebarBrand {{
    font-size: 13pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#SidebarVersion {{
    color: {MUTED};
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
    color: {MUTED};
    background: transparent;
    font-size: 10pt;
}}
QToolButton#Nav:hover {{
    background: {CARD_HOVER};
    color: {TEXT};
}}
QToolButton#Nav:checked {{
    background: rgba(91, 124, 250, 0.16);
    color: {TEXT};
    font-weight: 600;
}}

/* ---------------------------------------------------------------- 页面 */
QLabel#PageTitle {{
    font-size: 16pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#PageDesc {{
    color: {MUTED};
    font-size: 9pt;
}}
QLabel#Hint {{
    color: {MUTED};
    font-size: 9pt;
}}
QLabel#Empty {{
    color: {MUTED};
    font-size: 10pt;
    padding: 24px;
}}
QFrame#StatusBar {{
    background: #101216;
    border-top: 1px solid {BORDER};
}}
QFrame#Drawer {{
    background: #101216;
    border-top: 1px solid {BORDER};
}}
QLabel#DrawerTitle {{
    color: {MUTED};
    font-size: 9pt;
}}
QPushButton#Danger {{
    background: transparent;
    border: 1px solid rgba(255, 107, 107, 0.5);
    color: {RED};
    padding: 6px 12px;
    border-radius: 8px;
}}
QPushButton#Danger:hover {{
    background: rgba(255, 107, 107, 0.12);
}}
QPushButton#Danger:disabled {{
    color: #6a7284;
    border-color: #2a2f39;
    background: #1e2229;
}}
QScrollArea#PageScroll {{
    background: transparent;
    border: none;
}}
QScrollArea#PageScroll > QWidget > QWidget {{
    background: transparent;
}}
QListWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 0px;
    margin: 2px 0;
    border-radius: 8px;
    color: {TEXT};
}}
QListWidget::item:hover {{
    background: {CARD_HOVER};
}}
QListWidget::item:selected {{
    background: rgba(91, 124, 250, 0.20);
    color: {TEXT};
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
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#ffffff"))
        pen.setWidthF(4.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPolyline(QPolygon([QPoint(7, 17), QPoint(13, 23), QPoint(25, 9)]))
        p.end()
        pm.save(str(target), "PNG")
    return target.as_posix()


def stylesheet() -> str:
    try:
        icon = _check_icon()
    except Exception:
        icon = ""
    qss = QSS.replace("__CHECK__", icon)
    if not icon:
        qss = qss.replace('    image: url("");', "")
    return qss
