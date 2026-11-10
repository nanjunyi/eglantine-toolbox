"""侧边栏用的线性小图标：全部用 QPainter 现画，不依赖图片资源。

注意：``drawPolyline`` 传 Python list 在部分 PySide6 版本上会静默崩溃（退出码 127），
所以这里统一用 ``QPolygon([QPoint...])``。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygon

_CACHE: dict[tuple[str, str, int], QPixmap] = {}


def _pen(color: str, size: int) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.4, size / 11))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _poly(points: list[tuple[float, float]]) -> QPolygon:
    return QPolygon([QPoint(int(round(x)), int(round(y))) for x, y in points])


def _draw(name: str, p: QPainter, s: int) -> None:
    u = s / 18.0  # 以 18px 为设计基准
    if name == "play":
        p.drawPolygon(_poly([(6.2 * u, 4.4 * u), (14.2 * u, 9.0 * u), (6.2 * u, 13.6 * u)]))
    elif name == "saves":
        p.drawRoundedRect(QRectF(3.6 * u, 3.8 * u, 10.8 * u, 10.4 * u), 2.0 * u, 2.0 * u)
        p.drawRect(QRectF(6.6 * u, 3.8 * u, 4.6 * u, 3.4 * u))
        p.drawLine(QPointF(6.4 * u, 11.4 * u), QPointF(11.6 * u, 11.4 * u))
    elif name == "cheats":
        p.drawPolyline(_poly([(7.0 * u, 6.2 * u), (4.2 * u, 9.0 * u), (7.0 * u, 11.8 * u)]))
        p.drawPolyline(_poly([(11.0 * u, 6.2 * u), (13.8 * u, 9.0 * u), (11.0 * u, 11.8 * u)]))
        p.drawLine(QPointF(10.0 * u, 4.6 * u), QPointF(8.2 * u, 13.4 * u))
    elif name == "update":
        p.drawLine(QPointF(9.0 * u, 3.4 * u), QPointF(9.0 * u, 10.4 * u))
        p.drawPolyline(_poly([(6.0 * u, 7.6 * u), (9.0 * u, 10.6 * u), (12.0 * u, 7.6 * u)]))
        p.drawPolyline(
            _poly([(3.8 * u, 11.6 * u), (3.8 * u, 13.8 * u), (14.2 * u, 13.8 * u), (14.2 * u, 11.6 * u)])
        )
    elif name == "settings":
        p.drawEllipse(QRectF(6.6 * u, 6.6 * u, 4.8 * u, 4.8 * u))
        p.drawEllipse(QRectF(3.2 * u, 3.2 * u, 11.6 * u, 11.6 * u))
        for x1, y1, x2, y2 in (
            (9.0, 2.0, 9.0, 3.6),
            (9.0, 14.4, 9.0, 16.0),
            (2.0, 9.0, 3.6, 9.0),
            (14.4, 9.0, 16.0, 9.0),
        ):
            p.drawLine(QPointF(x1 * u, y1 * u), QPointF(x2 * u, y2 * u))
    else:  # 兜底：一个圆点，绝不空着
        p.drawEllipse(QRectF(7.0 * u, 7.0 * u, 4.0 * u, 4.0 * u))


def glyph(name: str, color: str, size: int = 18) -> QPixmap:
    key = (name, color, size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(_pen(color, size))
    painter.setBrush(Qt.NoBrush)
    _draw(name, painter, size)
    painter.end()
    _CACHE[key] = pm
    return pm


def glyph_icon(name: str, color: str, size: int = 18) -> QIcon:
    return QIcon(glyph(name, color, size))
