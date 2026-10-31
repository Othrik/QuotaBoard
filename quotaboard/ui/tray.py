"""系统托盘：最小化常驻、快速刷新、设置、开机自启、退出。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..config import Config
from ..scheduler import Scheduler
from .floating_window import FloatingWindow, make_app_icon

if TYPE_CHECKING:
    pass


def set_autostart(enabled: bool, exe_path: str) -> None:
    """写入/删除 HKCU 注册表 Run 项实现开机自启。"""
    import winreg
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                        winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "QuotaBoard", 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, "QuotaBoard")
            except FileNotFoundError:
                pass


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: FloatingWindow, scheduler: Scheduler,
                 config: Config) -> None:
        super().__init__(make_app_icon())
        self.window = window
        self.scheduler = scheduler
        self.config = config
        self.setToolTip("QuotaBoard · AI 额度悬浮窗")

        menu = QMenu()

        self.act_show = QAction("显示 / 隐藏悬浮窗", menu)
        self.act_show.triggered.connect(self.toggle_window)
        menu.addAction(self.act_show)

        act_refresh = QAction("立即刷新", menu)
        act_refresh.triggered.connect(self.scheduler.refresh_all)
        menu.addAction(act_refresh)

        act_settings = QAction("设置…", menu)
        act_settings.triggered.connect(self.open_settings)
        menu.addAction(act_settings)

        self.act_autostart = QAction("开机自启", menu)
        self.act_autostart.setCheckable(True)
        self.act_autostart.setChecked(self.config.startup_with_windows)
        self.act_autostart.toggled.connect(self.on_autostart_toggled)
        menu.addAction(self.act_autostart)

        menu.addSeparator()
        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_quit)

        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)

    def toggle_window(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()

    def on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_window()

    def on_autostart_toggled(self, checked: bool) -> None:
        self.config.startup_with_windows = checked
        self.config.save()
        exe = QApplication.applicationFilePath()
        try:
            set_autostart(checked, exe)
        except Exception as e:
            self.showMessage("QuotaBoard", f"设置开机自启失败：{e}",
                             QSystemTrayIcon.MessageIcon.Warning, 3000)
            self.act_autostart.blockSignals(True)
            self.act_autostart.setChecked(not checked)
            self.act_autostart.blockSignals(False)

    def open_settings(self) -> None:
        from .settings_dialog import SettingsDialog
        from PySide6.QtWidgets import QDialog
        dlg = SettingsDialog(self.config, self.window)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.scheduler.apply_interval()
            self.scheduler.refresh_all()
