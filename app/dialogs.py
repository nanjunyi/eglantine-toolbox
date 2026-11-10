"""公共对话框与「模拟器必须先退出」的交互封装。"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from .core import installer


def message(parent: QWidget, title: str, text: str, ok: str, icon) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(icon)
    box.addButton(ok, QMessageBox.AcceptRole)
    box.exec()


def info(parent: QWidget, title: str, text: str) -> None:
    message(parent, title, text, "知道了", QMessageBox.Information)


def error(parent: QWidget, title: str, text: str) -> None:
    message(parent, title, text, "关闭", QMessageBox.Warning)


def confirm(parent: QWidget, title: str, text: str, ok: str = "继续") -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Question)
    yes = box.addButton(ok, QMessageBox.AcceptRole)
    box.addButton("取消", QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is yes


def ensure_closed(parent: QWidget, action: str, log) -> bool:
    """模拟器在跑就先问一句，确认后 taskkill 并复查。"""
    if not installer.emulator_running():
        return True
    if not confirm(
        parent,
        "模拟器正在运行",
        f"检测到模拟器正在运行，{action}前需要先关闭它。\n是否现在关闭并继续？",
        "关闭并继续",
    ):
        return False
    installer.close_emulator(log)
    if installer.emulator_running():
        error(parent, "无法关闭模拟器", "请手动退出模拟器后重试。")
        return False
    return True


def human_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} 小时 {m} 分"
    if m:
        return f"{m} 分 {s} 秒"
    return f"{s} 秒"
