"""更新与汉化页：原「汉化工具」的全部功能搬到这里。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..core import buildinfo, installer
from ..core import release as rel
from ..core.common import human_size, resource_path
from ..dialogs import confirm, ensure_closed, error, info
from ..widgets import Badge, Card, ComboBox, ElidedLabel
from .base import Page


def _short(text: str, limit: int = 24) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class UpdatePage(Page):
    key = "update"

    def __init__(self, win) -> None:
        super().__init__(
            win,
            "更新与汉化",
            "选一个上游版本下载安装并汉化；也可只重建语言包或还原官方原版",
        )
        self._syncing = False

        self.badge = Badge("● 未检测", "muted")
        self.btn_net = QPushButton("网络设置")
        self.btn_net.setObjectName("Ghost")
        self.btn_net.clicked.connect(lambda: self.win.goto("settings"))
        self.add_header(self.btn_net)
        self.add_header(self.badge)

        self.body.addWidget(self._build_path_card())
        self.body.addWidget(self._build_version_card())
        self.body.addLayout(self._build_actions())
        self.body.addStretch(1)

        self.bus.busy_changed.connect(self.apply_busy)
        self.state.changed.connect(self.apply_state)
        self.state.releases_changed.connect(self._populate_versions)
        self.apply_state()

    # ------------------------------------------------------------------ 界面
    def _build_path_card(self) -> Card:
        card = Card(margins=(16, 12, 16, 12))
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel("安装位置")
        label.setObjectName("SectionLabel")
        label.setFixedWidth(56)
        self.path_label = ElidedLabel("未选择")
        self.path_label.setObjectName("Mono")
        self.btn_browse = QPushButton("浏览…")
        self.btn_browse.setObjectName("Ghost")
        self.btn_browse.clicked.connect(self._choose_dir)
        self.btn_open = QPushButton("打开目录")
        self.btn_open.setObjectName("Ghost")
        self.btn_open.clicked.connect(self._open_dir)
        row.addWidget(label)
        row.addWidget(self.path_label, 1)
        row.addWidget(self.btn_browse)
        row.addWidget(self.btn_open)
        card.body.addLayout(row)
        return card

    def _build_version_card(self) -> Card:
        card = Card()
        head = QHBoxLayout()
        head.setSpacing(8)
        sec = QLabel("版本")
        sec.setObjectName("SectionLabel")
        self.verdict = QLabel("尚未检查")
        self.verdict.setObjectName("Verdict")
        self.verdict.setStyleSheet(f"color: {theme.MUTED};")
        self.btn_check = QPushButton("检查更新")
        self.btn_check.setObjectName("Ghost")
        self.btn_check.clicked.connect(lambda: self.check_updates(silent=False))
        head.addWidget(sec)
        head.addWidget(self.verdict)
        head.addStretch(1)
        head.addWidget(self.btn_check)
        card.body.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(18)

        self.lbl_local_name = QLabel("—")
        self.lbl_local_name.setObjectName("Strong")
        self.lbl_local_tag = QLabel("—")
        self.lbl_local_tag.setObjectName("Mono")
        self.lbl_local_time = QLabel("—")
        self.lbl_local_time.setObjectName("Mono")
        cols.addLayout(
            self._version_column(
                "本地版本", self.lbl_local_name, self.lbl_local_tag, self.lbl_local_time
            ),
            1,
        )

        line = QWidget()
        line.setFixedWidth(1)
        line.setStyleSheet(f"background: {theme.BORDER};")
        cols.addWidget(line)

        self.lbl_remote_name = QLabel("—")
        self.lbl_remote_name.setObjectName("Strong")
        self.lbl_remote_tag = QLabel("—")
        self.lbl_remote_tag.setObjectName("Mono")

        target_col = QVBoxLayout()
        target_col.setSpacing(4)
        cap = QLabel("要安装的版本")
        cap.setObjectName("SectionLabel")
        target_col.addWidget(cap)
        self.combo_release = ComboBox()
        self.combo_release.setPlaceholderText("检查中…")
        self.combo_release.setMinimumWidth(280)
        self.combo_release.currentIndexChanged.connect(self._on_release_changed)
        target_col.addWidget(self.combo_release)
        target_col.addWidget(self.lbl_remote_name)
        target_col.addWidget(self.lbl_remote_tag)
        cols.addLayout(target_col, 1)

        card.body.addLayout(cols)
        return card

    @staticmethod
    def _version_column(title, name, tag, time_label) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(3)
        cap = QLabel(title)
        cap.setObjectName("SectionLabel")
        col.addWidget(cap)
        col.addWidget(name)
        col.addWidget(tag)
        col.addWidget(time_label)
        return col

    def _build_actions(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(10)
        self.btn_update = QPushButton("一键更新并汉化")
        self.btn_update.setObjectName("Primary")
        self.btn_update.setMinimumHeight(42)
        self.btn_update.clicked.connect(self.update_and_localize)
        self.btn_apply = QPushButton("仅应用汉化")
        self.btn_apply.setMinimumHeight(42)
        self.btn_apply.clicked.connect(self.apply_localization)
        self.btn_restore = QPushButton("还原官方原版")
        self.btn_restore.setMinimumHeight(42)
        self.btn_restore.clicked.connect(self.restore_original)
        self.btn_launch = QPushButton("启动模拟器")
        self.btn_launch.setMinimumHeight(42)
        self.btn_launch.clicked.connect(self.win.launch_emulator)

        grid.addWidget(self.btn_update, 0, 0)
        grid.addWidget(self.btn_apply, 0, 1)
        grid.addWidget(self.btn_restore, 1, 0)
        grid.addWidget(self.btn_launch, 1, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        return grid

    # ------------------------------------------------------------------ 状态
    def apply_state(self) -> None:
        state = self.state
        self.badge.set_state(*state.badge())
        self.path_label.setText(str(state.install_dir) if state.install_dir else "未选择")

        info_obj = state.info
        if not state.installed:
            self.lbl_local_name.setText("未安装")
            self.lbl_local_tag.setText("—")
            self.lbl_local_time.setText("点下方按钮全新安装")
        elif info_obj is not None:
            self.lbl_local_name.setText(info_obj.name or "Eglantine")
            self.lbl_local_tag.setText(info_obj.tag or "未识别到版本号")
            self.lbl_local_time.setText(
                f"commit {info_obj.short_commit} · 构建于 {info_obj.date_text}"
                if info_obj.commit
                else f"构建于 {info_obj.date_text}"
            )
        else:
            self.lbl_local_name.setText("—")
            self.lbl_local_tag.setText("读取失败")
            self.lbl_local_time.setText("—")

        self._refresh_verdict()
        self.apply_busy(self.bus.busy())

    def apply_busy(self, busy: bool) -> None:
        state = self.state
        has_dir = state.has_dir
        installed = state.installed
        can = not busy
        self.btn_browse.setEnabled(can)
        self.btn_net.setEnabled(can)
        self.btn_check.setEnabled(has_dir and can)
        self.btn_open.setEnabled(has_dir and can)
        self.combo_release.setEnabled(has_dir and can and bool(state.releases))
        self.btn_update.setEnabled(has_dir and can and bool(state.releases))
        for btn in (self.btn_apply, self.btn_restore, self.btn_launch):
            btn.setEnabled(installed and can)

    def _refresh_verdict(self) -> None:
        target = self.state.target
        info_obj = self.state.info
        if target is None:
            self.verdict.setText("尚未检查")
            self.verdict.setStyleSheet(f"color: {theme.MUTED};")
            self.btn_update.setText("一键更新并汉化")
            return
        if not self.state.installed:
            self._verdict(f"将全新安装 {target.channel_label} · {_short(target.tag, 22)}", theme.AMBER)
            self.btn_update.setText(f"安装 {_short(target.tag)} 并汉化")
        elif info_obj and rel.same_release(info_obj.tag, target):
            self._verdict("与本地版本一致", theme.GREEN)
            self.btn_update.setText("重新应用汉化")
        else:
            same_src = bool(
                info_obj
                and info_obj.commit
                and target.commit
                and (
                    target.commit.startswith(info_obj.commit[:10])
                    or info_obj.commit.startswith(target.commit[:10])
                )
            )
            note = "（同一 commit，仅打包时间不同）" if same_src else ""
            self._verdict(
                f"将安装 {target.channel_label} · {_short(target.tag, 22)}{note}", theme.AMBER
            )
            self.btn_update.setText(f"安装 {_short(target.tag)} 并汉化")

    def _verdict(self, text: str, color: str) -> None:
        self.verdict.setText(text)
        self.verdict.setStyleSheet(f"color: {color}; font-weight: 600;")

    # ------------------------------------------------------------------ 版本列表
    def _populate_versions(self) -> None:
        items = self.state.releases
        current = self.state.target.tag if self.state.target else ""
        self.combo_release.blockSignals(True)
        self.combo_release.clear()
        for item in items:
            self.combo_release.addItem(item.combo_text(), item.tag)
        idx = 0
        for i, item in enumerate(items):
            if item.tag == current:
                idx = i
                break
        if items:
            self.combo_release.setCurrentIndex(idx)
        self.combo_release.blockSignals(False)
        self._on_release_changed(idx)
        if items:
            self.log(f"可选版本 {len(items)} 个，默认选中 {items[idx].tag}")

    def _on_release_changed(self, index: int) -> None:
        items = self.state.releases
        if index < 0 or index >= len(items):
            return
        item = items[index]
        if item is not self.state.target:
            self.state.select(item.tag)

        asset = item.windows_asset
        self.lbl_remote_name.setText(item.name or item.tag)
        detail = item.date_text
        if asset:
            detail += f" · {human_size(asset.size)}"
        if item.commit:
            detail += f" · {item.commit[:10]}"
        self.lbl_remote_tag.setText(detail)
        tip = item.body or item.tag
        self.combo_release.setToolTip((tip[:800] + "…") if len(tip) > 800 else tip)
        self.combo_release.setItemData(index, self.combo_release.toolTip(), Qt.ToolTipRole)
        self._refresh_verdict()
        self.apply_busy(self.bus.busy())

    # ------------------------------------------------------------------ 检查更新
    def check_updates(self, silent: bool = False) -> None:
        if self.bus.busy():
            return
        if not silent:
            self.lbl_remote_name.setText("查询中…")
            self.lbl_remote_tag.setText("—")

        def task(prog):
            prog.stage("查询可选版本")
            releases = rel.fetch_releases(use_cache=silent, log=prog.log)
            items = rel.selectable(releases)
            if not items:
                raise rel.ReleaseError("仓库里没有找到带 Windows 安装包的版本")
            for item in items[:3]:
                prog.log(f"  · {item.combo_text()}")
            return items

        def done(items):
            self.state.set_releases(items)

        if not silent:
            self.log("—— 检查更新 ——")
        self.bus.run(task, done, label="检查更新", quiet=silent, preemptible=True)

    # ------------------------------------------------------------------ 操作
    def apply_localization(self) -> None:
        if not self._guard(need_exe=True) or not self._closed("应用汉化"):
            return

        def task(prog):
            return installer.localize(self.state.install_dir, resource_path("zh_CN.json"), prog)

        def done(stats):
            self.state.refresh()
            self.log("汉化完成，直接启动模拟器即为中文界面")
            extra = f"（其中 {stats['added']} 条为本工具补译）" if stats.get("added") else ""
            info(
                self,
                "汉化完成",
                f"中文词条 {stats['total']} 条{extra}。\n双击 eglantine.exe 或点「启动模拟器」即为中文界面。",
            )

        self.bus.run(task, done, label="应用汉化")

    def update_and_localize(self) -> None:
        if not self._guard(need_exe=False) or not self._closed("更新"):
            return

        target = self.state.target
        fresh = not self.state.installed
        same = self.state.same_as_local()
        if target is not None and not same:
            asset = target.windows_asset
            size = human_size(asset.size) if asset else "未知大小"
            where = "全新安装到" if fresh else "安装"
            if not confirm(
                self,
                "确认安装",
                f"将{where} {target.channel_label}：{target.tag}"
                + (f"（{target.name}）" if target.name and target.name != target.tag else "")
                + f"\n安装包 {size}，下载完成后自动{'安装' if fresh else '覆盖安装'}并汉化。\n\n"
                "用户配置（存档、按键、图形设置）保存在系统目录，不受影响。是否继续？",
                "开始安装",
            ):
                return

        def task(prog):
            chosen = target
            if chosen is None:
                prog.stage("查询可选版本")
                items = rel.selectable(rel.fetch_releases(log=prog.log))
                if not items:
                    raise rel.ReleaseError("仓库里没有找到带 Windows 安装包的版本")
                chosen = items[0]
            local = None
            if self.state.installed:
                try:
                    local = buildinfo.read_build_info(self.state.exe)
                except Exception as exc:  # noqa: BLE001
                    prog.log(f"本地版本读取失败（{exc}），按覆盖安装处理")
            if local and rel.same_release(local.tag, chosen):
                prog.log(f"本地 tag 已是 {chosen.tag}（按 tag 判定），跳过下载，仅重建汉化语言包")
                stats = installer.localize(self.state.install_dir, resource_path("zh_CN.json"), prog)
                return {"mode": "localize", "zh": stats, "tag": chosen.tag, "fresh": False}
            result = installer.update_and_localize(
                self.state.install_dir,
                chosen,
                resource_path("zh_CN.json"),
                prog,
                launch_after=bool(self.state.get("launch_after")),
            )
            result["mode"] = "update"
            result["fresh"] = fresh
            result["tag"] = chosen.tag
            return result

        def done(result):
            buildinfo.clear_cache()
            self.state.refresh()
            if result.get("mode") == "update":
                zh = result.get("zh") or {}
                verb = "已全新安装" if result.get("fresh") else "已安装"
                info(
                    self,
                    "安装完成",
                    f"{verb} {result.get('tag')} 并完成汉化。\n"
                    f"中文词条 {zh.get('total', 0)} 条。\n\n下次启动模拟器即为中文界面。",
                )
            else:
                info(self, "无需下载", "所选版本与本地一致，已重新生成中文语言包。")
            QTimer.singleShot(300, lambda: self.check_updates(silent=True))

        self.bus.run(task, done, label="安装并汉化")

    def restore_original(self) -> None:
        if not self._guard(need_exe=True):
            return
        if not confirm(
            self,
            "还原官方原版",
            "将把 eglantine.exe 恢复为官方原版（去掉中文补丁），"
            "界面语言改回英文，并移除中文语言包。\n\n"
            "模拟器设置、存档、按键配置都不会被删除。是否继续？",
            "确认还原",
        ):
            return
        if not self._closed("还原"):
            return

        def task(prog):
            return installer.restore_original(self.state.install_dir, prog)

        def done(result):
            self.state.refresh()
            info(self, "已还原", "已恢复为官方英文原版。需要中文时再点「仅应用汉化」即可。")

        self.bus.run(task, done, label="还原原版")

    # ------------------------------------------------------------------ 辅助
    def _guard(self, need_exe: bool = True) -> bool:
        state = self.state
        if state.has_dir and (state.installed or not need_exe):
            return True
        if need_exe:
            error(self, "没有找到模拟器", "请先点「浏览…」选择包含 eglantine.exe 的目录。")
        else:
            error(
                self,
                "还没有选择目录",
                "请先点「浏览…」选择一个目录：空目录会自动全新安装，已安装的目录会覆盖更新。",
            )
        return False

    def _closed(self, action: str) -> bool:
        return ensure_closed(self, action, self.log)

    def _open_dir(self) -> None:
        if self.state.has_dir:
            self.win.open_path(self.state.install_dir)

    def _choose_dir(self) -> None:
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        start = str(self.state.install_dir or self.win.app_dir())
        path = QFileDialog.getExistingDirectory(
            self, "选择安装目录（空目录会自动全新安装）", start
        )
        if not path:
            return
        candidate = Path(path)
        if not candidate.is_dir():
            error(self, "目录不对", "选择的路径不是一个文件夹。")
            return
        if not (candidate / installer.EXE).exists():
            try:
                others = sum(1 for _ in candidate.iterdir())
            except Exception:
                others = 0
            if others == 0:
                text = (
                    f"「{candidate}」是空目录。\n\n"
                    "接下来点「安装并汉化」，会先下载官方安装包，再安装并汉化。是否使用该目录？"
                )
            else:
                text = (
                    f"「{candidate}」里没有 eglantine.exe，但有 {others} 个文件/文件夹。\n\n"
                    "安装会写入并覆盖同名文件，但不会删除其它文件。是否使用该目录？"
                )
            if not confirm(self, "确认目录", text, "使用该目录"):
                return
        self.state.save()
        self.state.set_dir(candidate, log=self.log)
        self.check_updates(silent=True)
