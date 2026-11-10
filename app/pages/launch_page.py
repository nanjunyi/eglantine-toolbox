"""启动模拟器页：游戏列表 + 双击启动。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..core import eden, installer
from ..core.common import human_size
from ..dialogs import error, human_seconds
from ..widgets import Badge, Card, ElidedLabel
from .base import Page


class GameRow(QWidget):
    def __init__(self, game: eden.Game) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = ElidedLabel(game.title, mode=Qt.ElideRight)
        self.title.setObjectName("Strong")
        bits = []
        if game.title_id:
            bits.append(game.title_id)
        bits.append(human_size(game.size))
        if game.play_time:
            bits.append(f"已玩 {human_seconds(game.play_time)}")
        if game.last_played:
            bits.append(datetime.fromtimestamp(game.last_played).strftime("%m-%d %H:%M"))
        meta = ElidedLabel(" · ".join(bits), mode=Qt.ElideRight)
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


class LaunchPage(Page):
    key = "launch"

    def __init__(self, win) -> None:
        super().__init__(win, "启动模拟器", "列出游戏目录里的游戏，双击立刻开玩")
        self.games: list[eden.Game] = []
        self._filtered: list[eden.Game] = []

        self.body.addWidget(self._build_toolbar())
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setUniformItemSizes(False)
        self.list.setSpacing(2)
        self.list.itemDoubleClicked.connect(lambda _: self.launch_selected())
        self.list.currentRowChanged.connect(lambda _: self._sync_buttons())
        self.body.addWidget(self.list, 1)

        self.empty = QLabel("")
        self.empty.setObjectName("Empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.empty)

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
        self.sort.addItems(["最近游玩", "名称", "体积"])
        self.sort.currentIndexChanged.connect(lambda _: self._sort_games())
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("Ghost")
        btn_refresh.clicked.connect(lambda: self.reload(force=True))
        row.addWidget(self.search, 1)
        row.addWidget(self.sort)
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
        self.log(f"扫描到 {len(self.games)} 个游戏 · 游戏目录 {len(eden.game_dirs())} 个")
        self._sort_games()

    def _sort_games(self) -> None:
        mode = self.sort.currentIndex()
        if mode == 1:
            self.games.sort(key=lambda g: g.title.lower())
        elif mode == 2:
            self.games.sort(key=lambda g: g.size, reverse=True)
        else:
            self.games.sort(
                key=lambda g: (g.last_played, g.play_time, g.title.lower()), reverse=True
            )
        self._fill()

    def _fill(self) -> None:
        text = self.search.text().strip().lower()
        self._filtered = [
            g
            for g in self.games
            if not text or text in g.title.lower() or text in g.title_id.lower()
        ]
        self.list.clear()
        for game in self._filtered:
            item = QListWidgetItem()
            row = GameRow(game)
            item.setSizeHint(QSize(0, row.sizeHint().height() + 8))
            item.setData(Qt.UserRole, game.key)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        empty = not self._filtered
        if empty:
            self.empty.setText(
                "没有找到游戏。\n把游戏放进模拟器的游戏目录（qt-config.ini 的 Paths\\gamedirs），再点「刷新」。"
                if self.games
                else "还没有扫描到游戏文件（.nsp / .xci / .nup）。\n请在模拟器里添加游戏目录后点「刷新」。"
            )
        self.empty.setVisible(empty and self.state.installed)
        self.list.setVisible(not empty and self.state.installed)
        if not empty and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        self._sync_buttons()

    def selected_game(self) -> eden.Game | None:
        row = self.list.currentRow()
        if 0 <= row < len(self._filtered):
            return self._filtered[row]
        return None

    # ------------------------------------------------------------------ 操作
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
