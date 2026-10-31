"""QuotaBoard 入口：AI 额度桌面悬浮窗。

用法：
    python main.py
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.ui import FloatingWindow, SettingsDialog, TrayIcon


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("QuotaBoard")
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

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
