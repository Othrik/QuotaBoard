import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import Qt
from quotaboard.config import Config
from quotaboard.model import PLATFORM_META,QuotaResult
from quotaboard.scheduler import Scheduler
from quotaboard.ui.settings_dialog import SettingsDialog
from quotaboard.ui.floating_window import FloatingWindow
app=QApplication([])
for font in ('msyh.ttc','msyhbd.ttc','segoeui.ttf'):QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
app.setFont(QFont('Microsoft YaHei UI',9))
c=Config(Path('dist/display-preferences-test/config.json'))
c._data['platforms']={k:{'enabled':k in ('codex','gemini','doubao')} for k in PLATFORM_META}
c._data['platform_order']=list(PLATFORM_META)
c.set_floating_enabled('gemini',False)
w=FloatingWindow(c,Scheduler(c))
class Native:
    def set_rows(self,rows):self.rows=rows
w.native_taskbar=Native()
w.on_results({k:QuotaResult(k,PLATFORM_META[k]['label'],'80%') for k in ('codex','gemini','doubao')})
app.processEvents()
assert [r.platform for r in w.native_taskbar.rows]==['codex','gemini','doubao']
assert [w.body.itemAt(i).widget().findChild(QLabel,'platformName').text() for i in range(w.body.count())]==['ChatGPT','豆包']
assert [r.platform for r in w._dock_rows]==['codex','doubao']
d=SettingsDialog(c);d.navigation.setCurrentRow(1)
assert d.page_title.text()=='AI 显示顺序'
assert not d.order_buttons['上移'].isEnabled()
first=d.order_list.item(0).data(Qt.UserRole)
d._move_order_to(d.order_list.count()-1)
assert d.order_list.item(d.order_list.count()-1).data(Qt.UserRole)==first
assert not d.order_buttons['置底'].isEnabled()
d._move_order_to(0)
assert d.order_list.item(0).data(Qt.UserRole)==first
d._move_order(1)
assert d.order_list.item(1).text().startswith('02')
d._populate_order(list(PLATFORM_META))
assert not d.order_reset.isEnabled()
d.resize(980,780);d.show();app.processEvents();d.grab().save('dist/order-panel-preview.png')
d.hide();w.hide()
print('Floating-only exclusions preserve querying/taskbar, ordering page actions and boundaries passed')
