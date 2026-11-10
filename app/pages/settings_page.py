"""设置页：网络、路径、维护、关于。"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import __version__, theme
from ..constants import APP_NAME, DISPLAY_NAME, REPO, UPSTREAM_REPO
from ..core import eden, installer, saves
from ..core import release as rel
from ..core.common import human_size
from ..dialogs import confirm, error, info
from ..widgets import Card, ElidedLabel
from .base import Page


class SettingsPage(Page):
    key = "settings"

    def __init__(self, win) -> None:
        super().__init__(win, "设置", "网络、路径与维护")
        self.body.addWidget(self._build_network())
        self.body.addWidget(self._build_paths())
        self.body.addWidget(self._build_misc())
        self.body.addWidget(self._build_about())
        self.body.addStretch(1)
        self.state.changed.connect(self.apply_state)

    # ------------------------------------------------------------------ 网络
    def _build_network(self) -> Card:
        card = Card(margins=(16, 12, 16, 12), spacing=10)
        cap = QLabel("网络")
        cap.setObjectName("SectionLabel")
        card.body.addWidget(cap)

        self.chk_proxy = QCheckBox("使用系统代理（Clash / v2rayN 开着时保持勾选）")
        card.body.addWidget(self.chk_proxy)

        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel("加速源")
        label.setObjectName("SectionLabel")
        self.edit_mirror = QLineEdit()
        self.edit_mirror.setPlaceholderText("例如 https://gh-proxy.com/    留空表示直连")
        self.btn_test = QPushButton("测试连接")
        self.btn_test.setObjectName("Ghost")
        self.btn_test.clicked.connect(self.test_net)
        row.addWidget(label)
        row.addWidget(self.edit_mirror, 1)
        row.addWidget(self.btn_test)
        card.body.addLayout(row)

        self.net_result = QLabel("尚未测试")
        self.net_result.setObjectName("Hint")
        self.net_result.setWordWrap(True)
        card.body.addWidget(self.net_result)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_save_net = QPushButton("保存网络设置")
        self.btn_save_net.setObjectName("Primary")
        self.btn_save_net.clicked.connect(self.save_net)
        btn_row.addWidget(self.btn_save_net)
        card.body.addLayout(btn_row)
        return card

    # ------------------------------------------------------------------ 路径
    def _build_paths(self) -> Card:
        card = Card(margins=(16, 12, 16, 12), spacing=10)
        cap = QLabel("路径")
        cap.setObjectName("SectionLabel")
        card.body.addWidget(cap)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("模拟器目录"), 0, 0)
        self.path_install = ElidedLabel("—")
        self.path_install.setObjectName("Mono")
        btn_open_install = QPushButton("打开")
        btn_open_install.setObjectName("Ghost")
        btn_open_install.clicked.connect(self._open_install)
        grid.addWidget(self.path_install, 0, 1)
        grid.addWidget(btn_open_install, 0, 2)

        grid.addWidget(QLabel("存档备份"), 1, 0)
        self.edit_backup = QLineEdit()
        self.edit_backup.setPlaceholderText("留空＝工具目录\\backups")
        btn_pick = QPushButton("选择…")
        btn_pick.setObjectName("Ghost")
        btn_pick.clicked.connect(self._pick_backup)
        btn_open_backup = QPushButton("打开")
        btn_open_backup.setObjectName("Ghost")
        btn_open_backup.clicked.connect(self._open_backup)
        grid.addWidget(self.edit_backup, 1, 1)
        holder = QHBoxLayout()
        holder.setSpacing(6)
        holder.addWidget(btn_pick)
        holder.addWidget(btn_open_backup)
        grid.addLayout(holder, 1, 2)

        grid.addWidget(QLabel("模拟器数据"), 2, 0)
        self.path_data = ElidedLabel("—")
        self.path_data.setObjectName("Mono")
        btn_open_data = QPushButton("打开")
        btn_open_data.setObjectName("Ghost")
        btn_open_data.clicked.connect(lambda: self.win.open_path(eden.data_root()))
        grid.addWidget(self.path_data, 2, 1)
        grid.addWidget(btn_open_data, 2, 2)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)

        row = QHBoxLayout()
        self.chk_launch_after = QCheckBox("更新安装完成后自动启动模拟器")
        row.addWidget(self.chk_launch_after)
        row.addStretch(1)
        btn_save = QPushButton("保存路径设置")
        btn_save.clicked.connect(self.save_paths)
        row.addWidget(btn_save)
        card.body.addLayout(row)
        return card

    # ------------------------------------------------------------------ 维护
    def _build_misc(self) -> Card:
        card = Card(margins=(16, 12, 16, 12), spacing=10)
        cap = QLabel("维护")
        cap.setObjectName("SectionLabel")
        card.body.addWidget(cap)

        row = QHBoxLayout()
        row.setSpacing(8)
        btn_update = QPushButton("清理更新残留")
        btn_update.setObjectName("Ghost")
        btn_update.clicked.connect(self.clean_update)
        btn_repair = QPushButton("修复存档残留")
        btn_repair.setObjectName("Ghost")
        btn_repair.clicked.connect(self.repair_saves)
        btn_log = QPushButton("打开日志目录")
        btn_log.setObjectName("Ghost")
        btn_log.clicked.connect(lambda: self.win.open_path(self.win.log_file.parent))
        row.addWidget(btn_update)
        row.addWidget(btn_repair)
        row.addWidget(btn_log)
        row.addStretch(1)
        card.body.addLayout(row)

        self.misc_label = QLabel("")
        self.misc_label.setObjectName("Hint")
        card.body.addWidget(self.misc_label)
        return card

    # ------------------------------------------------------------------ 关于
    def _build_about(self) -> Card:
        card = Card(margins=(16, 12, 16, 12), spacing=6)
        cap = QLabel("关于")
        cap.setObjectName("SectionLabel")
        card.body.addWidget(cap)
        self.about = QLabel("")
        self.about.setObjectName("Hint")
        self.about.setWordWrap(True)
        card.body.addWidget(self.about)
        return card

    # ------------------------------------------------------------------ 数据
    def on_show(self) -> None:
        self.load_values()

    def load_values(self) -> None:
        cfg = self.state.cfg
        self.chk_proxy.setChecked(bool(cfg.get("use_system_proxy", True)))
        self.edit_mirror.setText(cfg.get("mirror", ""))
        self.chk_launch_after.setChecked(bool(cfg.get("launch_after", False)))
        self.edit_backup.setText(cfg.get("backup_dir", ""))
        self.apply_state()

    def apply_state(self) -> None:
        self.path_install.setText(str(self.state.install_dir or "未选择"))
        self.path_data.setText(str(eden.data_root()))
        self.net_result.setText(f"当前：{rel.describe_net()}")

        leftovers = saves.leftovers()
        update_dir = (self.state.install_dir / installer.UPDATE_DIR) if self.state.install_dir else None
        extra = ""
        if update_dir and update_dir.exists():
            size = sum(f.stat().st_size for f in update_dir.rglob("*") if f.is_file())
            extra = f"　·　更新临时文件 {human_size(size)}"
        self.misc_label.setText(
            (f"发现 {len(leftovers)} 个存档残留目录" if leftovers else "没有存档残留") + extra
        )

        info_obj = self.state.info
        emu = "未安装"
        if self.state.installed and info_obj is not None:
            emu = f"{info_obj.tag or '未知版本'}（{info_obj.date_text}）"
        self.about.setText(
            f"{DISPLAY_NAME} {__version__}\n"
            f"模拟器：{emu}\n"
            f"更新源：{UPSTREAM_REPO}\n"
            f"工具仓库：{REPO}\n"
            f"配置文件：工具目录下的 {APP_NAME}.json"
        )

    # ------------------------------------------------------------------ 操作
    def save_net(self) -> None:
        proxy = self.chk_proxy.isChecked()
        mirror = self.edit_mirror.text().strip()
        self.state.cfg["use_system_proxy"] = proxy
        self.state.cfg["mirror"] = mirror
        self.state.save()
        rel.set_net(proxy, mirror)
        self.net_result.setText(f"已保存 · {rel.describe_net()}")
        self.log(f"网络设置已更新：{rel.describe_net()}")

    def test_net(self) -> None:
        proxy = self.chk_proxy.isChecked()
        mirror = self.edit_mirror.text().strip()
        rel.set_net(proxy, mirror)
        self.btn_test.setEnabled(False)
        self.net_result.setText("正在测试…")

        def task(prog):
            try:
                return rel.ping(timeout=12)
            except Exception as exc:  # noqa: BLE001
                return f"连接失败：{exc}"

        def done(text):
            self.btn_test.setEnabled(True)
            self.net_result.setText(text)
            self.log(f"网络测试：{text}")

        if not self.bus.run(task, done, label="测试连接", quiet=True):
            self.btn_test.setEnabled(True)
            self.net_result.setText("有任务在运行，稍后再试")

    def save_paths(self) -> None:
        backup = self.edit_backup.text().strip()
        if backup:
            try:
                Path(backup).mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                error(self, "备份目录不可用", str(exc))
                return
        self.state.cfg["backup_dir"] = backup
        self.state.cfg["launch_after"] = self.chk_launch_after.isChecked()
        self.state.save()
        self.log(f"路径设置已保存（备份目录：{backup or '默认'}）")
        info(self, "已保存", "路径设置已生效。")

    def _pick_backup(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择存档备份目录", self.edit_backup.text() or str(Path.home()))
        if path:
            self.edit_backup.setText(path)

    def _open_install(self) -> None:
        if self.state.has_dir:
            self.win.open_path(self.state.install_dir)

    def _open_backup(self) -> None:
        path = saves.backup_root(self.state.get("backup_dir") or None)
        path.mkdir(parents=True, exist_ok=True)
        self.win.open_path(path)

    def clean_update(self) -> None:
        if not self.state.install_dir:
            return
        folder = self.state.install_dir / installer.UPDATE_DIR
        if not folder.exists():
            info(self, "没有残留", "没有更新临时目录。")
            return
        size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
        if not confirm(
            self,
            "清理更新残留",
            f"会删除 {folder}\n共 {human_size(size)}（含已下载的安装包）。\n\n"
            "删除后下次安装需要重新下载。是否继续？",
            "删除",
        ):
            return
        shutil.rmtree(folder, ignore_errors=True)
        self.log("已清理更新临时文件")
        self.apply_state()

    def repair_saves(self) -> None:
        items = saves.leftovers()
        if not items:
            info(self, "没有残留", "没有发现上次中断留下的临时目录。")
            return
        if not confirm(self, "修复存档残留", f"发现 {len(items)} 项残留，是否修复？", "开始修复"):
            return

        def task(prog):
            return saves.repair_leftovers(prog)

        def done(count):
            self.apply_state()
            info(self, "修复完成", f"处理了 {count} 项。")

        self.bus.run(task, done, label="修复存档残留")
