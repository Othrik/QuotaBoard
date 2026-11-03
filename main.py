"""QuotaBoard 入口：AI 额度桌面悬浮窗。

用法：
    python main.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QSharedMemory
from PySide6.QtWidgets import QApplication

from quotaboard.ui.floating_window import make_app_icon
from quotaboard import __version__
from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.ui import FloatingWindow, TrayIcon

SHARED_MEM_KEY = "QuotaBoard_single_instance"
# 持有引用，避免 QLockFile/QSharedMemory 被回收后锁提前释放
_INSTANCE_GUARDS: list = []


def _acquire_single_instance() -> QSharedMemory | None:
    """单实例：共享内存 + 文件锁双保险。
    共享内存已存在说明已有实例在运行，直接退出；共享内存在进程退出/被杀时
    由系统自动释放，不会残留锁。
    再叠一层文件锁，覆盖不同提权层级 / 不同会话各自启动的情况——两个实例
    同时写同一份任务栏状态会让任务栏组件反复重建浮层（小窗连续闪现）。"""
    shm = QSharedMemory(SHARED_MEM_KEY)
    if not shm.create(1):
        return None
    base = Path(os.environ.get("APPDATA") or Path.home()) / "QuotaBoard"
    base.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(base / "quotaboard.instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        shm.detach()
        return None
    _INSTANCE_GUARDS.extend([shm, lock])
    return shm


def main() -> int:
    if "--gemini-vss" in sys.argv:
        import gemini_vss_helper
        return gemini_vss_helper.main()
    shm = _acquire_single_instance()
    if shm is None:
        print("QuotaBoard 已在运行，本实例退出。")
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("QuotaBoard")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(make_app_icon())
    app.setQuitOnLastWindowClosed(False)

    config = Config()
    if "--taskbar" in sys.argv or "--no-taskbar" in sys.argv:
        config._data["taskbar_mode"] = "--taskbar" in sys.argv
        config.save()
    scheduler = Scheduler(config)
    window = FloatingWindow(config, scheduler)
    tray = TrayIcon(window, scheduler, config)
    from quotaboard.taskbar import TaskbarController
    window.native_taskbar = TaskbarController(config, window)
    window.native_taskbar.failed.connect(lambda message: tray.showMessage("QuotaBoard", message))
    app.aboutToQuit.connect(window.native_taskbar.stop)

    from quotaboard.ui.dashboard import Dashboard
    dashboard = Dashboard(config, scheduler)
    window.dashboard = dashboard
    dashboard.settings_saved.connect(lambda: (window.render(), scheduler.apply_interval(), scheduler.refresh_all()))

    def open_settings() -> None:
        dashboard.present()

    dashboard.taskbar_selection_changed.connect(window.native_taskbar.tick)
    dashboard.floating_selection_changed.connect(window.render)
    window.native_taskbar.details_requested.connect(lambda _platform: dashboard.present())
    window.native_taskbar.settings_requested.connect(open_settings)

    # 悬浮窗右键菜单信号
    window.refresh_requested.connect(scheduler.refresh_all)
    window.settings_requested.connect(open_settings)
    window.quit_requested.connect(app.quit)

    # 初始位置：屏幕右上角（不遮挡工作区左部）
    screen = app.primaryScreen().availableGeometry()
    window.adjustSize()
    window.move(screen.right() - window.width() - 28, screen.top() + 40)
    window.render()
    if not config._data.get("taskbar_mode", False):
        window.show()

    # 启动即拉取一次，随后按间隔自动刷新
    scheduler.start()
    scheduler.refresh_all()
    tray.show()
    if "--overview" in sys.argv:
        dashboard.present()

    code = app.exec()
    if shm is not None:
        shm.detach()
    return code


if __name__ == "__main__":
    sys.exit(main())
