# Taskbar Widgets integration

This package renders QuotaBoard inside the Windows taskbar through Taskbar Widgets 0.5.4+ native XAML renderer. It is separate from QuotaBoard's older taskbar-adjacent floating mode.

1. Run QuotaBoard 1.1.28 or later. It exports quota-only data to `%APPDATA%/QuotaBoard/taskbar-snapshot.json`.
2. Start Taskbar Widgets (https://github.com/pfcdev/TaskbarWidgets).
3. Settings > Developer > Install .twidget: choose `QuotaBoard-Taskbar.twidget`.
4. Review the package and approve installation yourself. Enable QuotaBoard in Installed Widgets.
5. Position the widget in the taskbar. QuotaBoard must remain running for refreshes. The old floating board can be hidden using its tray menu.

The widget rotates through enabled AIs every five seconds and exposes an expanded summary on hover. Data older than five minutes is marked cached. It does not read configuration, Cookie caches or API keys and does not request the network. Its PowerShell process nevertheless runs with ordinary Windows user rights (the host cannot technically enforce a narrower filesystem sandbox for this process type).

Private Windows taskbar APIs are used by the host. Windows updates may affect compatibility. Do not claim taskbar rendering verified until testing on the target build.

DeepSeek artwork: user-supplied `deepseek.svg`, rendered black on transparent background.
