"""Check edge-strip geometry, refresh and restoration without real credentials."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from quotaboard.config import Config
from quotaboard.model import QuotaResult
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow
app = QApplication([])
cfg = Config.__new__(Config)
cfg._data = {'platforms': {}, 'cache': {}}
w = FloatingWindow(cfg, Scheduler(cfg))
w.on_results({'codex': QuotaResult(platform='codex', label='ChatGPT', display='5h 66%', metrics=[{'label':'5h','percent':66},{'label':'周','percent':90}])})
w.show()
for edge in ('top', 'bottom', 'left', 'right'):
    w._dock_edge = edge
    w.update_size()
    app.processEvents()
    assert w.dock.isVisible() and not w.header.isVisible()
    assert w.width() > 60 and w.height() >= 30
    geo = w.screen().availableGeometry()
    if edge == 'top': assert w.y() == geo.top()
    if edge == 'bottom': assert w.y() + w.height() == geo.bottom() + 1
    if edge == 'left': assert w.x() == geo.left()
    if edge == 'right': assert w.x() + w.width() == geo.right() + 1
    w.on_results(w._results)
    app.processEvents()
    assert w._dock_edge == edge
w._dock_edge = None
w.update_size()
app.processEvents()
assert w.header.isVisible() and not w.dock.isVisible()
assert w.width() == 380
print('Dock geometry, refresh and restore passed')
