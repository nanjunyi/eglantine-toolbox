"""启动模拟器页：游戏列表 + 双击启动 + 右键管理（重命名 / 置顶 / 排序 / 隐藏）。"""

from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..core import eden, installer, prefs
from ..core.common import human_size
from ..dialogs import error, human_seconds
from ..widgets import Badge, Card, ElidedLabel
from .base import Page

SORT_LABELS = ["自定义顺序", "最近游玩", "名称", "体积"]
_HEX16 = re.compile(r"^[0-9A-Fa-f]{16}$")


class GameRow(QWidget):
    def __init__(self, game: eden.Game) -> None:
        super().__init__()
        # 整行对鼠标透明：点击/双击/右键都落到 QListWidget 的 viewport 上，
        # 否则点标题文字不会选中行（子控件吃掉了 press）。
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = ElidedLabel(game.title, mode=Qt.ElideRight, selectable=False)
        self.title.setObjectName("Strong")
        bits = []
        if game.title_id:
            bits.append(game.title_id)
        bits.append(human_size(game.size))
        if game.play_time:
            bits.append(f"已玩 {human_seconds(game.play_time)}")
        if game.last_played:
            bits.append(datetime.fromtimestamp(game.last_played).strftime("%m-%d %H:%M"))
        meta = ElidedLabel(" · ".join(bits), mode=Qt.ElideRight, selectable=False)
        meta.setObjectName("Mono")
        col.addWidget(self.title)
        col.addWidget(meta)
        lay.addLayout(col, 1)

        if game.updates:
            lay.addWidget(Badge("有更新", "info"), 0, Qt.AlignVCenter)
        if game.dlcs:
            lay.addWidget(Badge(f"DLC×{len(game.dlcs)}", "muted"), 0, Qt.AlignVCenter)
        if not game.installed:
            lay.addWidget(Badge("仅文件", "warn"), 0, Qt.AlignVCenter)
        if not game.recognized:
            lay.addWidget(Badge("未识别", "warn"), 0, Qt.AlignVCenter)


class HiddenDialog(QDialog):
    """列出没显示出来的条目，可恢复显示或关联 TitleID。"""

    def __init__(self, parent, items: list[tuple[eden.Game, str]]) -> None:
        super().__init__(parent)
        self.setWindowTitle("没有显示的游戏")
        self.resize(560, 380)
        self.chosen: tuple[eden.Game, str] | None = None
        self.action = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        tip = QLabel(
            "下面这些条目没在列表里。默认只显示模拟器识别过的游戏；\n"
            "文件名不带 TitleID 的游戏（.nup 等）可以「关联 TitleID」后正常显示。"
        )
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.list = QListWidget()
        for game, reason in items:
            row = QListWidgetItem(f"{game.title}　—　{reason}")
            row.setData(Qt.UserRole, game)
            row.setToolTip(str(game.launch_path or ""))
            self.list.addItem(row)
        lay.addWidget(self.list, 1)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        self.btn_show = QPushButton("恢复显示")
        self.btn_show.setObjectName("Primary")
        self.btn_show.clicked.connect(lambda: self._done("show"))
        self.btn_assoc = QPushButton("关联 TitleID…")
        self.btn_assoc.clicked.connect(lambda: self._done("assoc"))
        btn_close = QPushButton("关闭")
        btn_close.setObjectName("Ghost")
        btn_close.clicked.connect(self.reject)
        btns.addWidget(self.btn_show)
        btns.addWidget(self.btn_assoc)
        btns.addStretch(1)
        btns.addWidget(btn_close)
        lay.addLayout(btns)
        self.list.currentRowChanged.connect(self._sync)
        self.list.setCurrentRow(0)

    def _sync(self, _row: int = -1) -> None:
        game, _reason = self.selected()
        self.btn_show.setEnabled(game is not None)
        self.btn_assoc.setEnabled(game is not None and not game.title_id)

    def selected(self) -> tuple[eden.Game, str]:
        item = self.list.currentItem()
        if item is None:
            return None, ""
        return item.data(Qt.UserRole), item.text()

    def _done(self, action: str) -> None:
        game, reason = self.selected()
        if game is None:
            return
        self.chosen = (game, reason)
        self.action = action
        self.accept()


class LaunchPage(Page):
    key = "launch"

    def __init__(self, win) -> None:
        super().__init__(win, "启动模拟器", "只显示模拟器认得的游戏，双击立刻开玩")
        self.games: list[eden.Game] = []
        self._view: list[eden.Game] = []
        self._filtered: list[eden.Game] = []
        self._auto_fallback = False

        self.body.addWidget(self._build_toolbar())
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setUniformItemSizes(False)
        self.list.setSpacing(2)
        # 右键菜单挂在 QListWidget 上（挂 viewport 会被 viewportEvent 吞掉），
        # 信号里的 pos 是 viewport 坐标。
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._show_menu)
        self.list.itemDoubleClicked.connect(lambda _: self.launch_selected())
        self.list.currentRowChanged.connect(lambda _: self._sync_buttons())
        self.body.addWidget(self.list, 1)

        self.empty = QLabel("")
        self.empty.setObjectName("Empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.empty)

        self.hint = QLabel("")
        self.hint.setObjectName("Hint")
        self.body.addWidget(self.hint)

        self.run_label = QLabel("")
        self.run_label.setObjectName("Hint")
        self.body.addWidget(self.run_label)

        self.state.changed.connect(self.apply_state)
        self.timer = QTimer(self)
        self.timer.setInterval(2500)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self._poll()

    # ------------------------------------------------------------------ 界面
    def _build_toolbar(self) -> Card:
        card = Card(margins=(14, 10, 14, 10), spacing=8)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索游戏名或 TitleID…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self._fill())
        self.sort = QComboBox()
        self.sort.addItems(SORT_LABELS)
        self.sort.setCurrentIndex(prefs.sort_mode(self.state.cfg))
        self.sort.currentIndexChanged.connect(self._on_sort_changed)
        self.chk_all = QCheckBox("显示未识别")
        self.chk_all.setToolTip("把模拟器还没识别过的文件、以及没有 TitleID 的文件也列出来")
        self.chk_all.setChecked(prefs.show_all(self.state.cfg))
        self.chk_all.toggled.connect(self._on_show_all)
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("Ghost")
        btn_refresh.clicked.connect(lambda: self.reload(force=True))
        row.addWidget(self.search, 1)
        row.addWidget(self.sort)
        row.addWidget(self.chk_all)
        row.addWidget(btn_refresh)
        card.body.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.btn_launch = QPushButton("启动选中游戏")
        self.btn_launch.setObjectName("Primary")
        self.btn_launch.setMinimumHeight(38)
        self.btn_launch.clicked.connect(self.launch_selected)
        self.btn_plain = QPushButton("只启动模拟器")
        self.btn_plain.setMinimumHeight(38)
        self.btn_plain.clicked.connect(lambda: self.win.launch_emulator())
        self.btn_stop = QPushButton("关闭模拟器")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.setMinimumHeight(38)
        self.btn_stop.clicked.connect(self.close_emulator)
        row2.addWidget(self.btn_launch, 3)
        row2.addWidget(self.btn_plain, 2)
        row2.addWidget(self.btn_stop, 2)
        card.body.addLayout(row2)
        return card

    # ------------------------------------------------------------------ 数据
    def on_show(self) -> None:
        if not self.games:
            self.reload()

    def apply_state(self) -> None:
        if not self.state.installed:
            self.empty.setText("模拟器还没安装。请到「更新与汉化」页安装后再来。")
            self.empty.setVisible(True)
            self.list.setVisible(False)
            self.hint.setVisible(False)
            self._sync_buttons()
            return
        if not self.games:
            self.reload()
            return
        self._fill()

    def reload(self, force: bool = False) -> None:
        try:
            self.games = eden.load_games(use_cache=not force)
        except Exception as exc:  # noqa: BLE001
            error(self, "扫描游戏失败", str(exc))
            self.games = []
        self._apply_prefs()
        self.log(f"扫描到 {len(self.games)} 个游戏 · 游戏目录 {len(eden.game_dirs())} 个")
        self._fill()

    def _apply_prefs(self) -> None:
        """把「关联的 TitleID」「自定义名」「清理孤儿 key」应用到扫描结果。"""
        cfg = self.state.cfg
        changed = False
        for game in self.games:
            if not game.title_id:
                path = game.launch_path
                tid = prefs.assoc_tid(cfg, path) if path else ""
                if tid:
                    game.title_id = tid
                    game.key = tid
                    game.recognized = True
            if game.title_id:
                merged = prefs.display_title(cfg, game.title_id, game.title)
                if merged and merged != game.title:
                    game.title = merged
                    changed = True
        if self.games and prefs.prune(cfg, [g.key for g in self.games]):
            changed = True
        if changed:
            self.state.save()

    def _on_sort_changed(self, index: int) -> None:
        prefs.set_sort(self.state.cfg, index)
        self.state.save()
        self._fill()

    def _on_show_all(self, checked: bool) -> None:
        prefs.set_show_all(self.state.cfg, checked)
        self.state.save()
        self._fill()

    def _compute_view(self) -> None:
        cfg = self.state.cfg
        mode = prefs.sort_mode(cfg)
        ordered = prefs.order_games(self.games, cfg, mode)
        hidden = prefs.hidden(cfg)

        # 自动降级：一个都没被识别过（新机器 / 清过缓存）时不要给空白页
        self._auto_fallback = bool(ordered) and not any(g.recognized for g in ordered)

        base = [g for g in ordered if g.key not in hidden]
        show_all = prefs.show_all(cfg) or self._auto_fallback
        self._view = [g for g in base if show_all or g.recognized]

    def _fill(self) -> None:
        self._compute_view()
        text = self.search.text().strip().lower()
        self._filtered = [
            g
            for g in self._view
            if not text or text in g.title.lower() or text in g.title_id.lower()
        ]
        self.list.clear()
        for game in self._filtered:
            item = QListWidgetItem()
            row = GameRow(game)
            item.setSizeHint(QSize(0, row.sizeHint().height() + 8))
            item.setData(Qt.UserRole, game.key)
            path = game.launch_path
            item.setToolTip(
                f"{game.title}\n{game.title_id or '（无 TitleID）'}\n{path if path else ''}"
            )
            self.list.addItem(item)
            self.list.setItemWidget(item, row)

        empty = not self._filtered
        if empty:
            if self.games and (self._view or prefs.hidden(self.state.cfg)):
                self.empty.setText(
                    "没有匹配的游戏。\n清空搜索框，或右键「已隐藏的条目…」把隐藏的恢复回来。"
                )
            elif self.games:
                self.empty.setText(
                    "这些文件模拟器还没识别过。\n"
                    "勾选上方「显示未识别」可以先把它们列出来，或先进一次游戏再刷新。"
                )
            else:
                self.empty.setText(
                    "还没有扫描到游戏文件（.nsp / .xci / .nup）。\n"
                    "请在模拟器里添加游戏目录后点「刷新」。"
                )
        self.empty.setVisible(empty and self.state.installed)
        self.list.setVisible(not empty and self.state.installed)
        self._update_hint()
        if not empty and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        self._sync_buttons()

    def _update_hint(self) -> None:
        cfg = self.state.cfg
        hidden = prefs.hidden(cfg)
        shown = len(self._view)
        total = len(self.games)
        parts = []
        if self._auto_fallback:
            parts.append("模拟器还没识别过任何游戏，先按「显示全部」列出")
        elif not prefs.show_all(cfg) and total > shown:
            parts.append(f"显示 {shown} / {total} 个（默认只显示模拟器识别过的）")
        if hidden:
            parts.append(f"手动隐藏 {len(hidden)} 个")
        if parts:
            parts.append("右键可重命名、置顶、隐藏")
        self.hint.setText("　·　".join(parts))
        self.hint.setVisible(bool(parts))

    def selected_game(self) -> eden.Game | None:
        row = self.list.currentRow()
        if 0 <= row < len(self._filtered):
            return self._filtered[row]
        return None

    # ------------------------------------------------------------------ 菜单
    def _game_at(self, pos) -> eden.Game | None:
        row = self.list.indexAt(pos).row()
        if row < 0 or row >= len(self._filtered):
            return None
        self.list.setCurrentRow(row)
        return self._filtered[row]

    def _show_menu(self, pos) -> None:
        game = self._game_at(pos)
        if game is None:
            return
        self._build_menu(game).exec(self.list.viewport().mapToGlobal(pos))

    def _build_menu(self, game: eden.Game) -> QMenu:
        cfg = self.state.cfg
        pinned = prefs.is_pinned(cfg, game.key)
        custom = prefs.custom_title(cfg, game.title_id) if game.title_id else ""
        mode = prefs.sort_mode(cfg)
        manual_ok = mode == prefs.SORT_CUSTOM and not self.search.text().strip()

        menu = QMenu(self)
        menu.addAction("启动", self.launch_selected)
        menu.addSeparator()
        rename = menu.addAction("重命名…", lambda: self.rename_game(game))
        rename.setEnabled(bool(game.title_id) or bool(game.launch_path))
        if custom:
            menu.addAction("恢复原名", lambda: self.reset_name(game))
        menu.addSeparator()
        menu.addAction("取消置顶" if pinned else "置顶", lambda: self.toggle_pin(game))
        idx = next((i for i, g in enumerate(self._view) if g.key == game.key), -1)
        up = menu.addAction("上移", lambda: self.move_game(game, -1))
        down = menu.addAction("下移", lambda: self.move_game(game, 1))
        up.setEnabled(manual_ok and idx > 0)
        down.setEnabled(manual_ok and 0 <= idx < len(self._view) - 1)
        menu.addSeparator()
        if not game.title_id:
            menu.addAction("关联 TitleID…", lambda: self.associate(game))
        menu.addAction("从列表隐藏", lambda: self.hide_game(game))
        menu.addSeparator()
        copy_id = menu.addAction("复制 TitleID")
        copy_id.setEnabled(bool(game.title_id))
        copy_id.triggered.connect(lambda: self._copy_tid(game))
        menu.addAction("打开所在文件夹", lambda: self._open_folder(game))
        menu.addSeparator()
        menu.addAction("已隐藏的条目…", self.show_hidden)
        return menu

    # ------------------------------------------------------------------ 操作
    def rename_game(self, game: eden.Game) -> None:
        from PySide6.QtWidgets import QInputDialog

        cfg = self.state.cfg
        current = prefs.custom_title(cfg, game.title_id) or game.title
        title, ok = QInputDialog.getText(
            self,
            "重命名游戏",
            "显示名称（留空恢复原名）：\n"
            + (
                f"按 TitleID {game.title_id} 保存，重启后仍然有效"
                if game.title_id
                else "这个文件还没有 TitleID，先关联后改名才会长期生效"
            ),
            text=current,
        )
        if not ok:
            return
        if game.title_id:
            prefs.set_title(cfg, game.title_id, title)
            self.state.save()
            self.reload(force=False)
        else:
            game.title = title.strip() or game.title
            self._fill()
        self.log(f"重命名：{title.strip() or '（恢复原名）'}")

    def reset_name(self, game: eden.Game) -> None:
        prefs.clear_title(self.state.cfg, game.title_id)
        self.state.save()
        self.reload()

    def toggle_pin(self, game: eden.Game) -> None:
        cfg = self.state.cfg
        if prefs.is_pinned(cfg, game.key):
            prefs.unpin(cfg, game.key)
            self.log(f"取消置顶：{game.title}")
        else:
            prefs.pin(cfg, game.key)
            self.log(f"置顶：{game.title}")
        self.state.save()
        self._fill()

    def move_game(self, game: eden.Game, delta: int) -> None:
        keys = [g.key for g in self._view]
        if game.key not in keys:
            return
        i = keys.index(game.key)
        j = i + delta
        if j < 0 or j >= len(keys):
            return
        keys[i], keys[j] = keys[j], keys[i]
        cfg = self.state.cfg
        prefs.set_order(cfg, keys)
        prefs.set_sort(cfg, prefs.SORT_CUSTOM)
        self.state.save()
        self.sort.blockSignals(True)
        self.sort.setCurrentIndex(prefs.SORT_CUSTOM)
        self.sort.blockSignals(False)
        self._fill()
        self.list.setCurrentRow(j)

    def hide_game(self, game: eden.Game) -> None:
        prefs.hide(self.state.cfg, game.key)
        self.state.save()
        self.log(f"已隐藏：{game.title}（右键「已隐藏的条目…」可恢复）")
        self._fill()

    def associate(self, game: eden.Game) -> None:
        from PySide6.QtWidgets import QInputDialog

        used = {g.title_id.upper() for g in self.games if g.title_id}
        cands = [t for t in sorted(eden.recognized_ids()) if t not in used]
        path = game.launch_path
        if path is None:
            return
        hint = ("候选（模拟器日志里的）：" + "、".join(cands)) if cands else "没有可用候选，请手动填"
        text, ok = QInputDialog.getText(
            self,
            "关联 TitleID",
            f"给 {path.name} 指定 TitleID（16 位十六进制）：\n{hint}",
            text=cands[0] if cands else "",
        )
        if not ok:
            return
        tid = text.strip().upper()
        if not _HEX16.match(tid):
            error(self, "TitleID 不对", "需要 16 位十六进制，例如 04003F40232DE000。")
            return
        prefs.set_assoc(self.state.cfg, path, tid)
        self.state.save()
        self.log(f"已关联：{path.name} → {tid}")
        self.reload(force=True)

    def show_hidden(self) -> None:
        cfg = self.state.cfg
        shown = {g.key for g in self._view}
        items: list[tuple[eden.Game, str]] = []
        for game in self.games:
            if game.key in shown:
                continue
            reason = "已手动隐藏" if game.key in prefs.hidden(cfg) else "模拟器还没识别过"
            if not game.title_id:
                reason = "文件名没有 TitleID"
            items.append((game, reason))
        if not items:
            self.log("没有隐藏的条目")
            return
        dialog = HiddenDialog(self, items)
        if dialog.exec() != QDialog.Accepted:
            return
        game, _reason = dialog.chosen
        if dialog.action == "show":
            prefs.unhide(cfg, game.key)
            if not game.recognized:
                prefs.set_show_all(cfg, True)
                self.chk_all.blockSignals(True)
                self.chk_all.setChecked(True)
                self.chk_all.blockSignals(False)
            self.state.save()
            self._fill()
        else:
            self.associate(game)

    def _copy_tid(self, game: eden.Game) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(game.title_id)
        self.log(f"已复制 TitleID：{game.title_id}")

    def _open_folder(self, game: eden.Game) -> None:
        path = game.launch_path
        if path is not None:
            self.win.open_path(path.parent)

    def launch_selected(self) -> None:
        game = self.selected_game()
        if game is None:
            if len(self._filtered) == 1:
                game = self._filtered[0]
            else:
                error(self, "没有选游戏", "先在列表里点一个游戏。")
                return
        path = game.launch_path
        if path is None or not path.exists():
            error(self, "文件不见了", f"找不到游戏文件：\n{path}")
            return
        if self.win.launch_emulator(path):
            QTimer.singleShot(1500, self._poll)

    def close_emulator(self) -> None:
        if not installer.emulator_running():
            self._poll()
            return
        installer.close_emulator(self.log)
        self._poll()

    def _poll(self) -> None:
        running = installer.emulator_running()
        self.run_label.setText("● 模拟器运行中" if running else "● 模拟器未运行")
        self.run_label.setStyleSheet(f"color: {theme.GREEN if running else theme.MUTED};")
        self.btn_stop.setEnabled(running)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        installed = self.state.installed
        has_pick = self.selected_game() is not None
        self.btn_launch.setEnabled(installed and has_pick)
        self.btn_plain.setEnabled(installed)
        self.btn_stop.setEnabled(installer.emulator_running())
