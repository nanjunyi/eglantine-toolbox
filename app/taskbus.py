"""全局任务总线：同一时刻只跑一个后台任务。

页面化之后每个页面都可能发起任务（检查更新、下载、备份、还原…），
如果各自持有一个 QThread，就会出现「下载途中点了还原 → 老的被 cancel、
安装到一半被中断」这类危险情况。所以统一收敛到这里：

* 默认**不可抢占**（``preemptible=False``）：忙时直接拒绝，返回 False；
* 只有纯查询类的任务（检查更新）允许抢占；
* 归属判断用闭包里的 job 引用，不用 ``sender()``（多页面下会失效）。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .worker import Job


class TaskBus(QObject):
    busy_changed = Signal(bool)
    stage_changed = Signal(str)
    progress_changed = Signal(int, int, str)
    log_signal = Signal(str)
    finished = Signal(str, bool)  # label, ok
    failed = Signal(str, str)  # label, message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.job: Job | None = None
        self.label = ""
        self._preemptible = False

    # ------------------------------------------------------------------ 状态
    def busy(self) -> bool:
        return self.job is not None

    def cancel(self) -> None:
        if self.job is not None:
            self.job.cancel()

    # ------------------------------------------------------------------ 执行
    def run(
        self,
        task,
        on_done=None,
        label: str = "任务",
        quiet: bool = False,
        preemptible: bool = False,
    ) -> bool:
        if self.job is not None:
            # 只有「双方都可抢占」时才允许顶掉，避免查询类任务杀掉下载/备份
            if not (preemptible and self._preemptible):
                self.log_signal.emit(f"「{self.label}」还在进行中，请等它结束再操作")
                return False
            old = self.job
            old.cancel()
            old.wait(2500)
            self.job = None

        self._preemptible = bool(preemptible)
        job = Job(task, self)
        self.job = job
        self.label = label
        job.log_signal.connect(self.log_signal)
        job.stage_signal.connect(self.stage_changed)
        job.progress_signal.connect(self.progress_changed)
        job.failed_signal.connect(lambda msg, j=job: self._on_failed(j, msg, quiet))
        job.done_signal.connect(lambda result, j=job: self._on_done(j, result, on_done))
        self.busy_changed.emit(True)
        job.start()
        return True

    def _on_done(self, job: Job, result, callback) -> None:
        if self.job is not job:
            return
        label = self.label
        self.job = None
        self.busy_changed.emit(False)
        self.finished.emit(label, True)
        try:
            if callback is not None:
                callback(result)
        finally:
            job.deleteLater()

    def _on_failed(self, job: Job, message: str, quiet: bool) -> None:
        if self.job is not job:
            return
        label = self.label
        self.job = None
        self.busy_changed.emit(False)
        cancelled = message == "__cancelled__"
        if not cancelled:
            self.log_signal.emit(f"{label}失败：{message}")
        self.finished.emit(label, False)
        if not quiet:
            self.failed.emit(label, message)
        job.deleteLater()

    def wait(self, ms: int = 3000) -> None:
        if self.job is not None:
            job, self.job = self.job, None
            job.cancel()
            job.wait(ms)
            job.deleteLater()
            self.busy_changed.emit(False)
