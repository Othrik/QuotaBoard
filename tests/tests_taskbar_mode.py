import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from quotaboard.config import Config
from quotaboard.model import QuotaResult
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow
app=QApplication([]);c=Config.__new__(Config);c._data={'platforms':{},'cache':{}};c.save=lambda:None
w=FloatingWindow(c,Scheduler(c));w.on_results({'codex':QuotaResult(platform='codex',label='ChatGPT',display='5h 80% · 周 40%')})
w.show();app.processEvents()
w._dock_edge='taskbar';w.update_size();w._anchor_dock()
g=w.screen().availableGeometry();assert w.x()==g.left()+8;assert w.y()==g.bottom()+1-w.height()-6;assert w.width()<=360
w.move(100,100);w._keep_taskbar_position();assert w.x()==g.left()+8
w.set_taskbar_mode(True);app.processEvents()
assert c._data['taskbar_mode'] and not w.isVisible(),'托管任务栏模式下浮窗应隐藏'
w.set_taskbar_mode(False);assert w._dock_edge is None and w.width()==380
print('Taskbar placement, anchoring, persistence and disable passed')
