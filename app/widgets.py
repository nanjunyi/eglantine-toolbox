"""界面小组件：卡片、状态徽章、省略号标签、日志视图。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, margins=(16, 14, 16, 14), spacing=10):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(spacing)


class Badge(QLabel):
    COLORS = {
        "ok": theme.GREEN,
        "warn": theme.AMBER,
        "muted": theme.MUTED,
        "info": theme.ACCENT,
        "error": theme.RED,
    }

    def __init__(self, text: str = "", kind: str = "muted", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Badge")
        self.setAlignment(Qt.AlignCenter)
        self.set_state(text, kind)

    def set_state(self, text: str, kind: str = "muted") -> None:
        color = self.COLORS.get(kind, theme.MUTED)
        self.setText(text)
        self.setStyleSheet(
            f"background: rgba({_rgb(color)}, 0.16);"
            f"color: {color};"
            f"border: 1px solid rgba({_rgb(color)}, 0.35);"
            "border-radius: 10px; padding: 4px 12px; font-weight: 600;"
        )


def _rgb(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"{r}, {g}, {b}"


class ElidedLabel(QLabel):
    """超长路径自动省略中段，完整内容放在 tooltip。"""

    def __init__(self, text: str = "", parent=None, mode=Qt.ElideMiddle):
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setMinimumWidth(80)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt 命名)
        self._full = text or ""
        self.setToolTip(self._full)
        self._apply()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply()

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt 命名)
        # 不能按「已省略的文本」算尺寸，否则放进列表里会被压成一个点
        fm = QFontMetrics(self.font())
        hint = super().sizeHint()
        return QSize(min(fm.horizontalAdvance(self._full) + 8, 320), hint.height())

    def _apply(self) -> None:
        fm = QFontMetrics(self.font())
        width = max(self.width() - 4, 40)
        super().setText(fm.elidedText(self._full, self._mode, width))


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(4000)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setPlaceholderText("任务日志会显示在这里")

    def append_line(self, text: str) -> None:
        self.appendPlainText(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class ComboBox(QComboBox):
    """QComboBox + 自绘下箭头（QSS 覆盖样式后原生箭头会消失）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(theme.MUTED))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        w, h = 9, 5
        x = self.width() - 20
        y = (self.height() - h) // 2
        p.drawLine(x, y, x + w // 2, y + h)
        p.drawLine(x + w // 2, y + h, x + w, y)
        p.end()
