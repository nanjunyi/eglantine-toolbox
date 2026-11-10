"""金手指页：按游戏的 cheats 文件管理与编辑。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core import cheats, eden
from ..dialogs import confirm, error, info
from ..widgets import Badge, Card, ElidedLabel
from .base import Page


class CheatsPage(Page):
    key = "cheats"

    def __init__(self, win) -> None:
        super().__init__(win, "金手指", "写入 load\\<TitleID>\\cheats\\<build_id>.txt；每个游戏同时只生效一份")
        self.files: list[cheats.CheatFile] = []
        self._games: list[tuple[str, str]] = []  # (title_id, 显示名)
        self._loading = False

        self.body.addWidget(self._build_top())
        self.body.addWidget(self._build_files())
        self.body.addWidget(self._build_editor(), 1)

        self.state.changed.connect(self.apply_state)

    # ------------------------------------------------------------------ 界面
    def _build_top(self) -> Card:
        card = Card(margins=(14, 12, 14, 12), spacing=8)
        row = QHBoxLayout()
        row.setSpacing(8)
        cap = QLabel("游戏")
        cap.setObjectName("SectionLabel")
        self.combo_game = QComboBox()
        self.combo_game.setMinimumWidth(320)
        self.combo_game.currentIndexChanged.connect(lambda _: self._load_game())
        btn_reload = QPushButton("刷新")
        btn_reload.setObjectName("Ghost")
        btn_reload.clicked.connect(self.reload)
        row.addWidget(cap)
        row.addWidget(self.combo_game, 1)
        row.addWidget(btn_reload)
        card.body.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        cap2 = QLabel("build_id")
        cap2.setObjectName("SectionLabel")
        self.edit_build = QLineEdit()
        self.edit_build.setPlaceholderText("Eden 要求的 40 位 build id，可从日志读取或手填")
        self.edit_build.textChanged.connect(self._on_build_changed)
        btn_log = QPushButton("从日志读取")
        btn_log.setObjectName("Ghost")
        btn_log.clicked.connect(self.read_build_from_log)
        self.build_state = Badge("● 未设置", "muted")
        row2.addWidget(cap2)
        row2.addWidget(self.edit_build, 1)
        row2.addWidget(btn_log)
        row2.addWidget(self.build_state)
        card.body.addLayout(row2)

        self.path_label = ElidedLabel("", mode=Qt.ElideMiddle)
        self.path_label.setObjectName("Mono")
        card.body.addWidget(self.path_label)
        return card

    def _build_files(self) -> Card:
        card = Card(margins=(14, 12, 14, 12), spacing=8)
        head = QHBoxLayout()
        head.setSpacing(8)
        cap = QLabel("金手指文件")
        cap.setObjectName("SectionLabel")
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        head.addWidget(cap)
        head.addWidget(self.count_label)
        head.addStretch(1)
        self.btn_new = QPushButton("新建")
        self.btn_new.setObjectName("Ghost")
        self.btn_new.clicked.connect(self.do_new)
        self.btn_import = QPushButton("导入 txt…")
        self.btn_import.setObjectName("Ghost")
        self.btn_import.clicked.connect(self.do_import)
        self.btn_enable = QPushButton("启用选中")
        self.btn_enable.clicked.connect(self.do_enable)
        self.btn_disable = QPushButton("停用")
        self.btn_disable.setObjectName("Ghost")
        self.btn_disable.clicked.connect(self.do_disable)
        self.btn_delete = QPushButton("删除")
        self.btn_delete.setObjectName("Danger")
        self.btn_delete.clicked.connect(self.do_delete)
        for btn in (self.btn_new, self.btn_import, self.btn_enable, self.btn_disable, self.btn_delete):
            head.addWidget(btn)
        card.body.addLayout(head)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setMaximumHeight(120)
        self.list.currentRowChanged.connect(lambda _: self._load_file())
        card.body.addWidget(self.list)
        self.empty_hint = QLabel("这个游戏还没有金手指文件，点「新建」或「导入 txt…」")
        self.empty_hint.setObjectName("Hint")
        card.body.addWidget(self.empty_hint)
        return card

    def _build_editor(self) -> Card:
        card = Card(margins=(14, 12, 14, 12), spacing=8)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.file_label = ElidedLabel("未选择文件")
        self.file_label.setObjectName("Mono")
        self.stat_label = QLabel("")
        self.stat_label.setObjectName("Hint")
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("Primary")
        self.btn_save.clicked.connect(self.do_save)
        head.addWidget(self.file_label, 1)
        head.addWidget(self.stat_label)
        head.addWidget(self.btn_save)
        card.body.addLayout(head)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "[组名]\n040B0000 000216C0 2A1F03E0\n\n每组一个 [名字]，下面是代码行"
        )
        card.body.addWidget(self.editor, 1)
        return card

    # ------------------------------------------------------------------ 数据
    def on_show(self) -> None:
        if not self._games:
            self.reload()

    def apply_state(self) -> None:
        pass

    def reload(self) -> None:
        titles: dict[str, str] = {}
        try:
            for game in eden.load_games():
                if game.title_id:
                    titles[game.title_id] = game.title
        except Exception:
            pass
        for tid in cheats.game_ids_with_data():
            titles.setdefault(tid, "")
        self._games = [(tid, titles.get(tid) or f"游戏 {tid}") for tid in titles]

        current = self.current_tid()
        self.combo_game.blockSignals(True)
        self.combo_game.clear()
        for tid, name in self._games:
            self.combo_game.addItem(f"{name}  ·  {tid}", tid)
        if current:
            for i, (tid, _n) in enumerate(self._games):
                if tid == current:
                    self.combo_game.setCurrentIndex(i)
                    break
        self.combo_game.blockSignals(False)
        self._load_game()

    def current_tid(self) -> str:
        data = self.combo_game.currentData()
        return str(data) if data else ""

    def _load_game(self) -> None:
        tid = self.current_tid()
        self.files = []
        self.list.clear()
        self._loading = True
        try:
            self.editor.clear()
            self.file_label.setText("未选择文件")
            self.stat_label.setText("")
            if not tid:
                self.path_label.setText("")
                self.build_state.set_state("● 未设置", "muted")
                self._sync_buttons()
                return
            folder = cheats.cheats_dir(tid)
            self.path_label.setText(f"目录：{folder}")
            manual = (self.state.get("build_ids") or {}).get(tid, "")
            build = cheats.resolve_build_id(tid, manual)
            self.edit_build.setText(build)
            self._mark_build(build)
            self.files = cheats.list_cheats(tid)
            for item in self.files:
                label = item.label + ("  （生效中）" if item.enabled else "")
                self.list.addItem(label)
            if self.files:
                active_index = next((i for i, f in enumerate(self.files) if f.enabled), 0)
                self.list.setCurrentRow(active_index)
            self.count_label.setText(f"{len(self.files)} 份")
            self.empty_hint.setVisible(not self.files)
        finally:
            self._loading = False
            self._sync_buttons()

    def _mark_build(self, build: str) -> None:
        if build:
            self.build_state.set_state("● 已获取", "ok")
        else:
            self.build_state.set_state("● 需手填", "warn")

    def _on_build_changed(self, text: str) -> None:
        value = text.strip()
        self._mark_build(value)
        tid = self.current_tid()
        if not self._loading and tid:
            mapping = dict(self.state.get("build_ids") or {})
            if value:
                mapping[tid] = value.upper()
            else:
                mapping.pop(tid, None)
            self.state.cfg["build_ids"] = mapping
            self.state.save()

    def read_build_from_log(self) -> None:
        tid = self.current_tid()
        if not tid:
            return
        build = cheats.build_ids_from_log().get(tid, "")
        if not build:
            info(
                self,
                "日志里还没有",
                "没找到这个游戏的 build_id。\n"
                "请先用模拟器运行一次该游戏，再回来点「从日志读取」；也可以手动填。",
            )
            return
        self.edit_build.setText(build)

    def selected_file(self) -> cheats.CheatFile | None:
        row = self.list.currentRow()
        if 0 <= row < len(self.files):
            return self.files[row]
        return None

    def _load_file(self) -> None:
        if self._loading:
            return
        item = self.selected_file()
        if item is None:
            self.editor.clear()
            self.file_label.setText("未选择文件")
            self.stat_label.setText("")
            self._sync_buttons()
            return
        text = cheats.read(item.path)
        self.editor.setPlainText(text)
        self.file_label.setText(item.path.name)
        groups, codes = cheats.summary(text)
        self.stat_label.setText(f"{groups} 组 · {codes} 行代码" + ("　·　生效中" if item.enabled else ""))
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        busy = self.bus.busy()
        has_game = bool(self.current_tid())
        has_file = self.selected_file() is not None
        self.btn_new.setEnabled(has_game and not busy)
        self.btn_import.setEnabled(has_game and not busy)
        self.btn_enable.setEnabled(has_file and not busy and bool(self.edit_build.text().strip()))
        self.btn_disable.setEnabled(has_file and not busy)
        self.btn_delete.setEnabled(has_file and not busy)
        self.btn_save.setEnabled(has_file and not busy)
        self.editor.setReadOnly(not has_file)

    def apply_busy(self, busy: bool) -> None:
        self._sync_buttons()

    # ------------------------------------------------------------------ 操作
    def do_new(self) -> None:
        tid = self.current_tid()
        if not tid:
            return
        name, ok = QInputDialog.getText(self, "新建金手指", "文件名（不含 .txt）：", text="我的金手指")
        if not ok or not name.strip():
            return
        try:
            path = cheats.create(tid, name)
        except Exception as exc:  # noqa: BLE001
            error(self, "新建失败", str(exc))
            return
        self.log(f"新建 {path}")
        self._load_game()
        for i, item in enumerate(self.files):
            if item.path == path:
                self.list.setCurrentRow(i)
                break

    def do_import(self) -> None:
        tid = self.current_tid()
        if not tid:
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择金手指文件", "", "金手指 (*.txt)")
        if not path:
            return
        try:
            target = cheats.import_file(tid, Path(path))
        except Exception as exc:  # noqa: BLE001
            error(self, "导入失败", str(exc))
            return
        self.log(f"导入 {Path(path).name} → {target.name}")
        self._load_game()

    def do_save(self) -> None:
        item = self.selected_file()
        if item is None:
            return
        text = self.editor.toPlainText()
        problems = cheats.validate(text)
        if problems:
            preview = "\n".join(problems[:6])
            if not confirm(
                self,
                "格式可能有误",
                f"这些行看起来不像金手指代码（格式 TTTTTTTT AAAAAAAA VVVVVVVV）：\n\n{preview}\n\n仍然保存吗？",
                "仍然保存",
            ):
                return
        try:
            cheats.write(item.path, text)
        except Exception as exc:  # noqa: BLE001
            error(self, "保存失败", str(exc))
            return
        groups, codes = cheats.summary(text)
        self.stat_label.setText(f"{groups} 组 · {codes} 行代码" + ("　·　生效中" if item.enabled else ""))
        self.log(f"已保存 {item.path.name}（{groups} 组 / {codes} 行）")

    def do_enable(self) -> None:
        tid = self.current_tid()
        item = self.selected_file()
        build = self.edit_build.text().strip()
        if not tid or item is None or not build:
            return
        try:
            target = cheats.set_enabled(tid, item, build)
        except Exception as exc:  # noqa: BLE001
            error(self, "启用失败", str(exc))
            return
        self.log(f"已启用 {target.name}")
        self._load_game()
        info(
            self,
            "已启用",
            f"写入 {target.name}。\n重启 Eden 进游戏后，日志不再出现 No cheats file found 就是生效了。",
        )

    def do_disable(self) -> None:
        tid = self.current_tid()
        if not tid:
            return
        if cheats.disable(tid, self.edit_build.text().strip()):
            self.log("已停用金手指")
            self._load_game()
        else:
            info(self, "没有生效中的文件", "这个游戏当前没有启用中的金手指。")

    def do_delete(self) -> None:
        tid = self.current_tid()
        item = self.selected_file()
        if not tid or item is None:
            return
        if not confirm(self, "删除金手指", f"确定删除 {item.path.name} 吗？", "删除"):
            return
        cheats.remove(tid, item)
        self._load_game()
