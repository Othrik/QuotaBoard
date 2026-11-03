"""刷新调度器：QTimer 定时 + 线程池并行拉取各平台额度。"""
from __future__ import annotations

import dataclasses

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from .config import Config
from .model import PLATFORM_META, QuotaResult
from .providers import PROVIDERS
from .providers.base import Provider


class _TaskSignals(QObject):
    done = Signal(str, object)  # platform_key, QuotaResult


class _RefreshTask(QRunnable):
    def __init__(self, key: str, provider: Provider) -> None:
        super().__init__()
        self.key = key
        self.provider = provider
        self.signals = _TaskSignals()

    def run(self) -> None:
        try:
            result = self.provider.fetch()
        except Exception as e:  # 兜底：任何异常都转为失败结果，不崩溃
            result = QuotaResult(
                platform=self.key, label=getattr(self.provider, "label", self.key),
                display="—", ok=False, error=str(e))
        self.signals.done.emit(self.key, result)


class Scheduler(QObject):
    """管理刷新节奏；每轮完成后统一发 refreshed 信号。"""

    result_ready = Signal(str, object)
    refresh_started = Signal()
    refreshed = Signal(dict)  # {platform_key: QuotaResult}

    def __init__(self, config: Config, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self.pool = QThreadPool(self)
        self.pending: dict[str, QuotaResult] = {}
        self.expected = 0
        self.running = False

    def start(self) -> None:
        self.apply_interval()
        self.timer.start()

    def apply_interval(self) -> None:
        self.timer.setInterval(self.config.refresh_interval_minutes * 60 * 1000)

    def refresh_all(self) -> None:
        if self.running:
            return
        keys = [k for k in PROVIDERS if self.config.is_enabled(k)]
        if not keys:
            self.refreshed.emit({})
            return
        self.running = True
        self.refresh_started.emit()
        self.expected = len(keys)
        self.pending = {}
        for key in keys:
            provider_cls = PROVIDERS[key]
            task = _RefreshTask(key, provider_cls(self._provider_cfg(key)))
            task.signals.done.connect(self._on_done)
            self.pool.start(task)

    def _provider_cfg(self, key: str) -> dict:
        meta = PLATFORM_META[key]
        cfg = {field: self.config.get_credential(key, field)
               for field, _ in meta["credential_fields"]}
        if key == "volc":
            cfg["action"] = self.config.platform_cfg(key).get("action", "GetUsageDetails")
        return cfg

    def _on_done(self, key: str, result: QuotaResult) -> None:
        self.pending[key] = result
        try:
            self.config.set_cache(key, dataclasses.asdict(result))
        except TypeError:
            pass
        self.result_ready.emit(key, result)
        if len(self.pending) >= self.expected:
            self.running = False
            try:
                self.config.save()  # 一轮结束后统一落盘缓存
            except Exception:
                pass
            self.refreshed.emit(dict(self.pending))
