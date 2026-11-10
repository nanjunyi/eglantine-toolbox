"""程序图标（不依赖 Pillow：用 Qt 绘制后打包为 ICO）。"""

from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap


def draw_icon(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    rect = QRectF(size * 0.03, size * 0.03, size * 0.94, size * 0.94)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, QColor("#4f6fe6"))
    grad.setColorAt(1.0, QColor("#8a5cf6"))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(rect, size * 0.22, size * 0.22)

    p.setPen(QColor(255, 255, 255, 240))
    font = QFont("Microsoft YaHei UI")
    font.setWeight(QFont.Bold)
    font.setPixelSize(int(size * 0.52))
    p.setFont(font)
    p.drawText(rect, Qt.AlignCenter, "汉")
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_icon(s))
    return icon


def _png_bytes(pm: QPixmap) -> bytes:
    arr = QByteArray()
    buf = QBuffer(arr)
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(arr.data())


def write_ico(path: Path, sizes=(16, 24, 32, 48, 64, 128, 256)) -> Path:
    """写一个多尺寸 ICO（各尺寸用 PNG 负载，Vista+ 支持）。"""
    images = [(s, _png_bytes(draw_icon(s))) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,
            0,
            1,
            32,
            len(data),
            offset + len(blobs),
        )
        blobs += data
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + blobs)
    return path
