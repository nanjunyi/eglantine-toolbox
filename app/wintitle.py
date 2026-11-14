"""Windows 标题栏跟随主题（DWM 属性），主窗与对话框共用。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QWidget

from . import theme


def colorref(hex_color: str) -> int:
    """#RRGGBB → Windows COLORREF（0x00BBGGRR，低字节是 R）。"""
    c = (hex_color or "").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        return 0
    return (b << 16) | (g << 8) | r


def apply_titlebar(window: QWidget, dark: bool | None = None) -> bool:
    """Windows 10/11 的标题栏跟随主题（否则亮色窗体顶着一条黑杠很割裂）。

    走 DWM：20/19 开关 immersive dark mode，35/34（Win11）把标题栏与边框染成主题色。
    任何一步失败都静默跳过，不影响使用；属性幂等，可反复调用。
    """
    if sys.platform != "win32":
        return False
    if dark is None:
        dark = theme.is_dark()
    try:
        import ctypes

        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi

        def set_attr(attr: int, value: int) -> None:
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(data), ctypes.sizeof(data))

        flag = 1 if dark else 0
        set_attr(20, flag)  # DWMWA_USE_IMMERSIVE_DARK_MODE
        set_attr(19, flag)  # 旧版系统同义属性
        pal = theme.DARK if dark else theme.LIGHT
        set_attr(35, colorref(pal.BG))  # DWMWA_CAPTION_COLOR
        set_attr(34, colorref(pal.BORDER))  # DWMWA_BORDER_COLOR
        return True
    except Exception:
        return False
