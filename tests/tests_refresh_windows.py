"""A refresh must never show a transient, unparented quota label window."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QApplication, QWidget
from quotaboard.config import Config
from quotaboard.model import QuotaResult
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow, _Row

app = QApplication([])

class WindowWatch(QObject):
    def __init__(self):
        super().__init__()
        self.shown = []
    def eventFilter(self, widget, event):
        if event.type() == QEvent.Show and isinstance(widget, QWidget) and widget.isWindow():
            self.shown.append(type(widget).__name__)
        return False

watch = WindowWatch()
app.installEventFilter(watch)
results = [
    QuotaResult(platform='zhipu_member', label='积分', display='100', updated_at='2026-11-04 04:00:00'),
    QuotaResult(platform='codex', label='ChatGPT', display='80%',
                sub_note='5h重置 08:00 · 周重置 11-07 20:01',
                metrics=[dict(label='5h', percent=80)]),
    QuotaResult(platform='gemini', label='Gemini', display='—', error='测试请求失败'),
]
for result in results:
    row = _Row(result)
    app.processEvents()
    assert not watch.shown, f'Quota row construction opened windows: {watch.shown}'
    row.deleteLater()

cfg = Config.__new__(Config)
cfg._data = dict(platforms={r.platform:dict(enabled=True) for r in results},
                 platform_order=[r.platform for r in results], cache={}, taskbar_mode=True)
cfg.save = lambda: None
board = FloatingWindow(cfg, Scheduler(cfg))
for _ in range(5):
    for result in results:
        board.on_partial_result(result.platform, result)
    board.on_results({r.platform:r for r in results})
    app.processEvents()
    assert not watch.shown, f'Hidden taskbar-mode refresh opened windows: {watch.shown}'
assert not board.isVisible()
print('Quota row construction and five refresh rounds opened no top-level windows')
