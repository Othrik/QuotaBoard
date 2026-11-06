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
MUTEX_NAME = "Local\\QuotaBoard.SingleInstance.v1"
# 持有引用，避免 QLockFile/QSharedMemory/互斥量句柄被回收后锁提前释放
_INSTANCE_GUARDS: list = []
_MUTEX_HANDLE = None


def _acquire_windows_mutex() -> bool:
    """内核互斥量：两个实例几乎同时启动时也能只有一个拿到，
    返回 False 表示已有实例在跑。拿不到句柄时不拦，交给后面的文件锁兜底。"""
    global _MUTEX_HANDLE
    if os.name != "nt":
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return True
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return False
    _MUTEX_HANDLE = handle
    _INSTANCE_GUARDS.append(handle)
    return True


def _acquire_single_instance() -> QSharedMemory | None:
    """单实例：内核互斥量 + 共享内存 + 文件锁三层。
    任何一层判定已有实例就直接退出；两个实例同时写同一份任务栏状态会让
    任务栏组件反复重建浮层（小窗连续闪现、桌面跟着闪）。"""
    if not _acquire_windows_mutex():
        return None
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
    if _MUTEX_HANDLE:
        try:
            import ctypes
            ctypes.WinDLL("kernel32").CloseHandle(_MUTEX_HANDLE)
        except Exception:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
