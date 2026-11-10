"""页面基类：统一的标题区 + 可滚动内容区。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class Page(QWidget):
    key = "page"

    def __init__(self, win, title: str, desc: str = "") -> None:
        super().__init__()
        self.win = win
        self.state = win.state
        self.bus = win.bus

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 12)
        outer.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("PageTitle")
        self.desc_label = QLabel(desc)
        self.desc_label.setObjectName("PageDesc")
        self.desc_label.setVisible(bool(desc))
        texts.addWidget(self.title_label)
        texts.addWidget(self.desc_label)
        header.addLayout(texts)
        header.addStretch(1)
        self.header = header
        outer.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("PageScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("PageContent")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(12)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)

    # ------------------------------------------------------------------ 钩子
    def add_header(self, widget: QWidget) -> None:
        self.header.addWidget(widget, 0, Qt.AlignVCenter)

    def on_show(self) -> None:  # 切到本页时调用
        pass

    def apply_state(self) -> None:  # 全局状态变化时调用
        pass

    def apply_busy(self, busy: bool) -> None:  # 任务开始/结束时调用
        pass

    # ------------------------------------------------------------------ 便捷
    def log(self, text: str) -> None:
        self.win.log(text)
