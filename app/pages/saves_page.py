"""游戏存档页：备份 / 还原 / 导入 / 导出。"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import eden, prefs, saves
from ..core.common import human_size
from ..dialogs import confirm, ensure_closed, error, info
from ..widgets import Card, ElidedLabel
from .base import Page


class SaveRow(QWidget):
    def __init__(self, entry: saves.SaveEntry, title: str) -> None:
        super().__init__()
        # 同 GameRow：整行透明，点击才落到 viewport 上（否则点标题选不中）。
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(2)
        name = ElidedLabel(title, mode=Qt.ElideRight, selectable=False)
        name.setObjectName("Strong")
        meta = ElidedLabel(
            f"{entry.title_id} · {human_size(entry.size)} · "
            f"{time.strftime('%m-%d %H:%M', time.localtime(entry.mtime))}",
            mode=Qt.ElideRight,
            selectable=False,
        )
        meta.setObjectName("Mono")
        lay.addWidget(name)
        lay.addWidget(meta)


class BackupRow(QWidget):
    def __init__(self, item: saves.Backup) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(2)
        label = ("自动快照 · " if item.auto else "") + item.when
        if item.note and not item.auto:
            label += f" · {item.note}"
        name = QLabel(label)
        name.setObjectName("Strong")
        meta = QLabel(f"{human_size(item.size)} · {item.files} 个文件")
        meta.setObjectName("Mono")
        lay.addWidget(name)
        lay.addWidget(meta)


class SavesPage(Page):
    key = "saves"

    def __init__(self, win) -> None:
        super().__init__(win, "游戏存档", "备份到本地 zip；还原前会自动留一份快照")
        self.entries: list[saves.SaveEntry] = []
        self.backups: list[saves.Backup] = []
        self._titles: dict[str, str] = {}

        self.body.addWidget(self._build_hint())

        cols = QHBoxLayout()
        cols.setSpacing(12)
        left = self._build_left()
        left.setMinimumWidth(330)
        left.setMaximumWidth(380)
        cols.addWidget(left)
        cols.addWidget(self._build_right(), 1)
        self.body.addLayout(cols, 1)

        self.state.changed.connect(self.apply_state)

    # ------------------------------------------------------------------ 界面
    def _build_hint(self) -> Card:
        card = Card(margins=(14, 10, 14, 10), spacing=6)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.where = ElidedLabel("", mode=Qt.ElideMiddle)
        self.where.setObjectName("Hint")
        btn_open_save = QPushButton("打开存档目录")
        btn_open_save.setObjectName("Ghost")
        btn_open_save.clicked.connect(lambda: self.win.open_path(saves.container_dir()))
        btn_open_backup = QPushButton("打开备份目录")
        btn_open_backup.setObjectName("Ghost")
        btn_open_backup.clicked.connect(self._open_backup_root)
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("Ghost")
        btn_refresh.clicked.connect(self.reload)
        row.addWidget(self.where, 1)
        row.addWidget(btn_refresh)
        row.addWidget(btn_open_save)
        row.addWidget(btn_open_backup)
        card.body.addLayout(row)
        return card

    def _build_left(self) -> Card:
        card = Card(margins=(12, 12, 12, 12), spacing=8)
        title = QLabel("有存档的游戏")
        title.setObjectName("SectionLabel")
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._show_menu)
        self.list.currentRowChanged.connect(lambda _: self._load_backups())
        card.body.addWidget(title)
        card.body.addWidget(self.list, 1)
        return card

    def _build_right(self) -> Card:
        card = Card(margins=(14, 12, 14, 12), spacing=8)
        self.current_label = QLabel("请选择一个游戏")
        self.current_label.setObjectName("Strong")
        self.path_label = ElidedLabel("", mode=Qt.ElideMiddle)
        self.path_label.setObjectName("Mono")
        card.body.addWidget(self.current_label)
        card.body.addWidget(self.path_label)

        self.backup_list = QListWidget()
        self.backup_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.backup_list.currentRowChanged.connect(lambda _: self._sync_buttons())
        card.body.addWidget(self.backup_list, 1)
        self.backup_empty = QLabel("还没有备份，点「立即备份」存一份")
        self.backup_empty.setObjectName("Empty")
        self.backup_empty.setAlignment(Qt.AlignCenter)
        card.body.addWidget(self.backup_empty)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_backup = QPushButton("立即备份")
        self.btn_backup.setObjectName("Primary")
        self.btn_backup.setMinimumHeight(38)
        self.btn_backup.clicked.connect(self.do_backup)
        self.btn_restore = QPushButton("还原选中")
        self.btn_restore.setMinimumHeight(38)
        self.btn_restore.clicked.connect(self.do_restore)
        self.btn_delete = QPushButton("删除选中")
        self.btn_delete.setObjectName("Danger")
        self.btn_delete.setMinimumHeight(38)
        self.btn_delete.clicked.connect(self.do_delete)
        row.addWidget(self.btn_backup, 3)
        row.addWidget(self.btn_restore, 2)
        row.addWidget(self.btn_delete, 2)
        card.body.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.btn_import = QPushButton("导入备份…")
        self.btn_import.setObjectName("Ghost")
        self.btn_import.clicked.connect(self.do_import)
        self.btn_export = QPushButton("导出选中…")
        self.btn_export.setObjectName("Ghost")
        self.btn_export.clicked.connect(self.do_export)
        self.btn_repair = QPushButton("修复残留")
        self.btn_repair.setObjectName("Ghost")
        self.btn_repair.clicked.connect(self.do_repair)
        row2.addWidget(self.btn_import)
        row2.addWidget(self.btn_export)
        row2.addWidget(self.btn_repair)
        row2.addStretch(1)
        card.body.addLayout(row2)
        return card

    # ------------------------------------------------------------------ 数据
    def on_show(self) -> None:
        if not self.entries:
            self.reload()

    def apply_state(self) -> None:
        text = f"备份目录：{self._backup_root()}　·　存档：{saves.container_dir()}"
        self.where.setText(text)
        self.where.setToolTip(f"存档目录：{saves.container_dir()}\n备份目录：{self._backup_root()}")

    def reload(self) -> None:
        try:
            self._titles = {g.title_id: g.title for g in eden.load_games() if g.title_id}
        except Exception:
            self._titles = {}
        try:
            self.entries = saves.list_saves()
        except Exception as exc:  # noqa: BLE001
            error(self, "读取存档失败", str(exc))
            self.entries = []
        self.list.clear()
        for entry in self.entries:
            item = QListWidgetItem()
            title = self._title_of(entry.title_id)
            row = SaveRow(entry, title)
            item.setSizeHint(QSize(0, row.sizeHint().height() + 6))
            item.setToolTip(f"{title}\n{entry.path}")
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        self.apply_state()
        if self.entries:
            self.list.setCurrentRow(0)
        else:
            self._load_backups()
        self.log(f"存档：{len(self.entries)} 个游戏")

    def _title_of(self, title_id: str) -> str:
        fallback = self._titles.get(title_id.upper(), "")
        return prefs.display_title(self.state.cfg, title_id, fallback)

    def _show_menu(self, pos) -> None:
        row = self.list.indexAt(pos).row()
        if row < 0 or row >= len(self.entries):
            return
        self.list.setCurrentRow(row)
        entry = self.entries[row]
        menu = QMenu(self)
        menu.addAction("重命名…", lambda: self.rename_game(entry))
        menu.addAction("打开存档所在目录", lambda: self.win.open_path(entry.path))
        menu.addSeparator()
        menu.addAction("刷新", self.reload)
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def rename_game(self, entry: saves.SaveEntry) -> None:
        from PySide6.QtWidgets import QInputDialog

        cfg = self.state.cfg
        current = prefs.custom_title(cfg, entry.title_id) or self._title_of(entry.title_id)
        name, ok = QInputDialog.getText(
            self,
            "重命名游戏",
            f"显示名称（留空恢复默认）：\n按 TitleID {entry.title_id} 保存，启动页与金手指页同样生效",
            text=current,
        )
        if not ok:
            return
        prefs.set_title(cfg, entry.title_id, name)
        self.state.save()
        self.reload()
        self.log(f"重命名存档：{name.strip() or '（恢复默认）'}")

    def _backup_root(self) -> Path:
        return saves.backup_root(self.state.get("backup_dir") or None)

    def _open_backup_root(self) -> None:
        path = self._backup_root()
        path.mkdir(parents=True, exist_ok=True)
        self.win.open_path(path)

    def selected(self) -> saves.SaveEntry | None:
        row = self.list.currentRow()
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None

    def selected_backup(self) -> saves.Backup | None:
        row = self.backup_list.currentRow()
        if 0 <= row < len(self.backups):
            return self.backups[row]
        return None

    def _load_backups(self) -> None:
        entry = self.selected()
        self.backup_list.clear()
        self.backups = []
        if entry is None:
            self.current_label.setText("请选择一个游戏")
            self.path_label.setText("")
            self._sync_buttons()
            return
        self.current_label.setText(self._title_of(entry.title_id))
        self.path_label.setText(str(entry.path))
        try:
            self.backups = saves.list_backups(entry.title_id, self.state.get("backup_dir") or None)
        except Exception as exc:  # noqa: BLE001
            error(self, "读取备份失败", str(exc))
        for item in self.backups:
            row = QListWidgetItem()
            widget = BackupRow(item)
            row.setSizeHint(QSize(0, widget.sizeHint().height() + 6))
            row.setToolTip(f"{item.path.name}\n{item.path}")
            self.backup_list.addItem(row)
            self.backup_list.setItemWidget(row, widget)
        self.backup_list.setVisible(bool(self.backups))
        self.backup_empty.setVisible(not self.backups and entry is not None)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        busy = self.bus.busy()
        has_entry = self.selected() is not None
        has_backup = self.selected_backup() is not None
        can = not busy
        self.btn_backup.setEnabled(has_entry and can)
        self.btn_restore.setEnabled(has_entry and has_backup and can)
        self.btn_delete.setEnabled(has_backup and can)
        self.btn_export.setEnabled(has_backup and can)
        self.btn_import.setEnabled(can)
        self.btn_repair.setEnabled(can and bool(saves.leftovers()))

    def apply_busy(self, busy: bool) -> None:
        self._sync_buttons()

    # ------------------------------------------------------------------ 操作
    def do_backup(self) -> None:
        entry = self.selected()
        if entry is None:
            return
        from ..core import installer

        if installer.emulator_running() and not confirm(
            self,
            "模拟器还在运行",
            "备份时模拟器正在写存档，可能抓到写了一半的文件。\n"
            "建议先关掉模拟器再备份。仍要继续吗？",
            "仍然备份",
        ):
            return
        title = self._title_of(entry.title_id)

        def task(prog):
            return saves.backup(
                entry.title_id,
                entry.uid,
                self.state.get("backup_dir") or None,
                progress=prog,
            )

        def done(result):
            self._load_backups()
            info(self, "备份完成", f"{title}\n{human_size(result.size)} → {result.path.name}")

        self.bus.run(task, done, label="备份存档")
        self._sync_buttons()

    def do_restore(self) -> None:
        entry = self.selected()
        item = self.selected_backup()
        if entry is None or item is None:
            return
        if not confirm(
            self,
            "还原存档",
            f"将用「{item.when}」的备份覆盖当前存档：\n{entry.path}\n\n"
            "还原前会自动再存一份快照，出问题还能退回来。是否继续？",
            "开始还原",
        ):
            return
        if not ensure_closed(self, "还原", self.log):
            return

        def task(prog):
            return saves.restore(item.path, prog, uid=entry.uid)

        def done(result):
            self.reload()
            extra = f"\n还原前的旧存档：{result.previous.name}" if result.previous else ""
            info(self, "还原完成", f"已还原 {result.files} 个文件。{extra}")

        self.bus.run(task, done, label="还原存档")
        self._sync_buttons()

    def do_delete(self) -> None:
        item = self.selected_backup()
        if item is None:
            return
        if not confirm(self, "删除备份", f"确定删除这个备份吗？\n{item.path.name}", "删除"):
            return
        try:
            item.path.unlink()
        except OSError as exc:
            error(self, "删除失败", str(exc))
            return
        self._load_backups()

    def do_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择存档备份", "", "存档备份 (*.zip)")
        if not path:
            return
        try:
            result = saves.import_zip(
                Path(path), self.state.get("backup_dir") or None
            )
        except Exception as exc:  # noqa: BLE001
            error(self, "导入失败", str(exc))
            return
        self.log(f"已导入 {Path(path).name} → {result.title_id}")
        # 选中对应游戏
        for i, entry in enumerate(self.entries):
            if entry.title_id == result.title_id:
                self.list.setCurrentRow(i)
                break
        self._load_backups()
        info(self, "导入完成", f"已收进备份列表：{result.path.name}\n选中它点「还原选中」才会写入存档。")

    def do_export(self) -> None:
        item = self.selected_backup()
        if item is None:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "导出备份到", f"{item.title_id}-{item.path.stem}.zip", "存档备份 (*.zip)"
        )
        if not target:
            return
        try:
            saves.export(item.path, Path(target))
        except Exception as exc:  # noqa: BLE001
            error(self, "导出失败", str(exc))
            return
        self.log(f"已导出到 {target}")

    def do_repair(self) -> None:
        items = saves.leftovers()
        if not items:
            info(self, "没有残留", "没有发现上次中断留下的临时目录。")
            self._sync_buttons()
            return
        text = "\n".join(p.name for p in items[:8])
        if not confirm(
            self,
            "修复残留",
            f"发现 {len(items)} 个残留目录：\n{text}\n\n"
            "临时目录会被删除；被中断的还原会自动恢复回去。是否继续？",
            "开始修复",
        ):
            return

        def task(prog):
            return saves.repair_leftovers(prog)

        def done(count):
            self.reload()
            info(self, "修复完成", f"处理了 {count} 项。")

        self.bus.run(task, done, label="修复存档残留")
