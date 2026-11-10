"""左侧导航栏。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .glyphs import glyph_icon
from .icon import draw_icon


class NavButton(QToolButton):
    def __init__(self, key: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName("Nav")
        self.setText(f"   {text}")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(18, 18))
        self.setMinimumHeight(38)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.toggled.connect(self._sync_icon)

    def load_icon(self, name: str) -> None:
        self._glyph_name = name
        self._sync_icon(self.isChecked())

    def _sync_icon(self, checked: bool) -> None:
        name = getattr(self, "_glyph_name", "")
        if not name:
            return
        color = theme.TEXT if checked or self.underMouse() else theme.MUTED
        self.setIcon(glyph_icon(name, color))


class Sidebar(QFrame):
    selected = Signal(int)

    ITEMS = [
        ("launch", "play", "启动模拟器"),
        ("saves", "saves", "游戏存档"),
        ("cheats", "cheats", "金手指"),
        ("update", "update", "更新与汉化"),
        ("settings", "settings", "设置"),
    ]

    def __init__(self, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(208)
        self.buttons: list[NavButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(16, 18, 16, 14)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(draw_icon(34))
        logo.setFixedSize(34, 34)
        title = QLabel("Eglantine")
        title.setObjectName("SidebarBrand")
        brand.addWidget(logo)
        brand.addWidget(title)
        brand.addStretch(1)
        outer.addLayout(brand)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("SidebarScroll")
        holder = QWidget()
        holder.setObjectName("SidebarHolder")
        col = QVBoxLayout(holder)
        col.setContentsMargins(10, 4, 10, 10)
        col.setSpacing(4)

        for index, (key, glyph, label) in enumerate(self.ITEMS):
            btn = NavButton(key, label)
            btn.load_icon(glyph)
            btn.clicked.connect(lambda _=False, i=index: self.selected.emit(i))
            col.addWidget(btn)
            self.buttons.append(btn)
        col.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        self.footer = QLabel(version)
        self.footer.setObjectName("SidebarVersion")
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setContentsMargins(0, 0, 0, 12)
        outer.addWidget(self.footer)

        self.set_current(0)

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
            self.selected.emit(index)

    def select_key(self, key: str) -> None:
        for i, btn in enumerate(self.buttons):
            if btn.key == key:
                self.set_current(i)
                return
