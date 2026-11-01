"""QuotaBoard 入口：AI 额度桌面悬浮窗。

用法：
    python main.py
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QDialog

from quotaboard.ui.floating_window import make_app_icon
from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.ui import FloatingWindow, SettingsDialog, TrayIcon

SHARED_MEM_KEY = "QuotaBoard_single_instance"


def _acquire_single_instance() -> QSharedMemory | None:
    """单实例：共享内存已存在说明已有实例在运行，直接退出。
    共享内存在进程退出/被杀时由系统自动释放，不会残留锁。"""
    shm = QSharedMemory(SHARED_MEM_KEY)
    if not shm.create(1):
        return None
    return shm


def main() -> int:
    shm = _acquire_single_instance()
    if shm is None:
        print("QuotaBoard 已在运行，本实例退出。")
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("QuotaBoard")
    app.setWindowIcon(make_app_icon())
    app.setQuitOnLastWindowClosed(False)

    config = Config()
    scheduler = Scheduler(config)
    window = FloatingWindow(config, scheduler)
    tray = TrayIcon(window, scheduler, config)

    def open_settings() -> None:
        dlg = SettingsDialog(config, window)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            scheduler.apply_interval()
            scheduler.refresh_all()

    # 悬浮窗右键菜单信号
    window.refresh_requested.connect(scheduler.refresh_all)
    window.settings_requested.connect(open_settings)
    window.quit_requested.connect(app.quit)

    # 初始位置：屏幕右上角（不遮挡工作区左部）
    screen = app.primaryScreen().availableGeometry()
    window.adjustSize()
    window.move(screen.right() - window.width() - 28, screen.top() + 40)
    window.show()

    # 启动即拉取一次，随后按间隔自动刷新
    scheduler.start()
    scheduler.refresh_all()
    tray.show()

    code = app.exec()
    if shm is not None:
        shm.detach()
    return code


if __name__ == "__main__":
    sys.exit(main())
