"""GUI 冒烟测试：启动悬浮窗与托盘，3 秒后自动退出，验证无崩溃。

运行：python tests_gui_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quotaboard.config import Config  # noqa: E402
from quotaboard.scheduler import Scheduler  # noqa: E402
from quotaboard.ui import FloatingWindow, TrayIcon  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("QuotaBoard-Smoke")

    config = Config()
    scheduler = Scheduler(config)
    window = FloatingWindow(config, scheduler)
    tray = TrayIcon(window, scheduler, config)

    screen = app.primaryScreen().availableGeometry()
    window.adjustSize()
    window.move(screen.right() - window.width() - 28, screen.top() + 40)
    window.show()
    tray.show()

    # 模拟一次刷新（无启用平台，应安全返回空结果）
    scheduler.refresh_all()
    window.render()

    def check() -> None:
        assert window.isVisible(), "悬浮窗应可见"
        app.quit()

    QTimer.singleShot(2500, check)
    rc = app.exec()
    print("GUI 冒烟测试通过")
    return rc


if __name__ == "__main__":
    sys.exit(main())
