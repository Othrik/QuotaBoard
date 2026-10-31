"""UI 包：悬浮窗、设置、托盘。"""
from .floating_window import FloatingWindow, make_app_icon
from .settings_dialog import SettingsDialog
from .tray import TrayIcon

__all__ = ["FloatingWindow", "SettingsDialog", "TrayIcon", "make_app_icon"]
