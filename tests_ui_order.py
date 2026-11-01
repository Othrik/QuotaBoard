import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtCore import Qt
from quotaboard.config import Config
from quotaboard.model import QuotaResult,PLATFORM_META
from quotaboard.scheduler import Scheduler
from quotaboard.ui.settings_dialog import SettingsDialog
from quotaboard.ui.floating_window import FloatingWindow
app=QApplication([])
c=Config.__new__(Config);c._data={'platforms':{},'cache':{},'refresh_interval_minutes':1,'platform_order':['doubao','codex','doubao','removed']};c.save=lambda:None
assert c.platform_order[:2]==['doubao','codex']
assert len(c.platform_order)==len(PLATFORM_META)
d=SettingsDialog(c)
i=next(i for i in range(d.order_list.count()) if d.order_list.item(i).data(Qt.ItemDataRole.UserRole)=='gemini')
item=d.order_list.takeItem(i);d.order_list.insertItem(0,item);d._save()
assert c.platform_order[0]=='gemini'
w=FloatingWindow(c,Scheduler(c));w.on_results({k:QuotaResult(platform=k,label=PLATFORM_META[k]['label'],display='OK') for k in ['codex','gemini','doubao']})
assert [w.body.itemAt(i).widget().findChildren(QLabel)[1].text() for i in range(3)]==['Gemini','豆包','ChatGPT']
w._dock_edge='top';w.update_size()
assert [w.dock_layout.itemAt(i).widget().toolTip().splitlines()[0] for i in range(3)]==['Gemini','豆包','ChatGPT']
print('Order normalization, save, board and dock order passed')
