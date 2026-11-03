"""Overview updates stay in-place, including hidden refreshes and preferences."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QFontDatabase, QFont
from quotaboard.config import Config
from quotaboard.model import QuotaResult, PLATFORM_META
from quotaboard.scheduler import Scheduler
from quotaboard.ui.dashboard import Dashboard
from quotaboard.taskbar import rotation_candidates

app = QApplication([])
for font in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
app.setFont(QFont('Microsoft YaHei UI', 9))
config = Config(Path('dist/dashboard-test/config.json'))
config._data['cache'] = {}
for key in PLATFORM_META:
    config.set_enabled(key, key in ('codex', 'gemini', 'doubao', 'zhipu_member', 'deepseek', 'dmxapi'))
    config.set_taskbar_enabled(key, True)
    config.set_floating_enabled(key, True)
scheduler = Scheduler(config)
dashboard = Dashboard(config, scheduler)
assert len(dashboard.cards) == len(PLATFORM_META)
rows = [
    QuotaResult('codex','ChatGPT','5h 82% · 周 44%', metrics=[dict(label='5h',percent=82,note='5h 重置 18:42'),dict(label='周',percent=44,note='周重置 11-07 20:01')]),
    QuotaResult('gemini','Gemini','5h 98% · 周 99%', sub_note='PRO · 5h 重置 20:30 · 周重置 11-09 22:29',metrics=[dict(label='5h',percent=98,note='5h 重置 20:30'),dict(label='周',percent=99.0329,note='周重置 11-09 22:29')]),
    QuotaResult('doubao','豆包','0%', metrics=[dict(label='5h',percent=0),dict(label='周',percent=0)],sub_note='11月5日 03:04 周重置'),
    QuotaResult('zhipu_member','智谱清言','积分 23,859.98'),
    QuotaResult('deepseek','DeepSeek','¥ 86.42'),
    QuotaResult('dmxapi','DMXAPI','—',ok=False,error='连接暂时不可用，下一轮自动重试'),
]
for row in rows:
    scheduler.result_ready.emit(row.platform, row)
assert dashboard.cards['codex'].metric_rows[0][2].text() == '82%'
assert dashboard.cards['gemini'].metric_rows[1][2].text() == '99%'
assert dashboard.cards['gemini'].note.text().count('重置 20:30') == 1
assert dashboard.cards['dmxapi'].status.text() == '请求失败'
assert dashboard.cards['openai'].status.text() == '未启用'
changes=[]
dashboard.taskbar_selection_changed.connect(lambda: changes.append(True))
dashboard.cards['gemini'].taskbar_check.setChecked(False)
assert config.is_enabled('gemini') and not config.is_taskbar_enabled('gemini')
assert Config(config.path).is_taskbar_enabled('gemini') is False
assert 'gemini' not in [r.platform for r in rotation_candidates(rows,config._data['platforms'])]
assert 'doubao' in [r.platform for r in rotation_candidates(rows,config._data['platforms'])]
assert 'dmxapi' not in [r.platform for r in rotation_candidates(rows,config._data['platforms'])]
scheduler.result_ready.emit('gemini',rows[1])
assert not dashboard.cards['gemini'].taskbar_check.isChecked()
assert dashboard.cards['gemini'].metric_rows[1][2].text() == '99%'
assert changes == [True], 'refresh must not save or toggle selection'
dashboard.cards['gemini'].taskbar_check.setChecked(True)
assert 'gemini' in [r.platform for r in rotation_candidates(rows,config._data['platforms'])]
assert config.is_taskbar_enabled('unknown-new-platform'), 'existing installs default to included'
floating_changes=[]
dashboard.floating_selection_changed.connect(lambda:floating_changes.append(True))
dashboard.cards['gemini'].floating_check.setChecked(False)
assert config.is_enabled('gemini') and config.is_taskbar_enabled('gemini')
assert not Config(config.path).is_floating_enabled('gemini')
scheduler.result_ready.emit('gemini',rows[1])
assert not dashboard.cards['gemini'].floating_check.isChecked()
assert dashboard.results['gemini'].ok and floating_changes==[True]
dashboard.filter.setCurrentIndex(1)
assert sum(not c.isHidden() for c in dashboard.cards.values()) == 6
dashboard.search.setText('Gemini')
assert sum(not c.isHidden() for c in dashboard.cards.values()) == 1
dashboard.search.clear()
dashboard.filter.setCurrentIndex(2)
assert not dashboard.cards['dmxapi'].isHidden()
assert not dashboard.cards['doubao'].isHidden()
assert dashboard.cards['gemini'].isHidden()
dashboard.filter.setCurrentIndex(1)
dashboard.resize(1000,800)
dashboard.present();app.processEvents()
card_ids = {k:id(c) for k,c in dashboard.cards.items()}
scheduler.running = True
scheduler.refresh_started.emit()
assert not dashboard.refresh_button.isEnabled()
scheduler.running = False
scheduler.refreshed.emit({r.platform:r for r in rows})
assert dashboard.refresh_button.isEnabled()
assert {k:id(c) for k,c in dashboard.cards.items()} == card_ids
Path('dist').mkdir(exist_ok=True)
dashboard.grab().save('dist/dashboard-preview.png')
dashboard.open_preferences('gemini');app.processEvents()
preferences = dashboard.preferences
assert preferences.navigation.currentItem().data(Qt.UserRole) == 'gemini'
preferences.hide()
dashboard.open_preferences('deepseek')
assert dashboard.preferences is preferences
preferences.hide();dashboard.hide();app.processEvents()

class Watch(QObject):
    def __init__(self):super().__init__();self.shown=[]
    def eventFilter(self,widget,event):
        if event.type()==QEvent.Show and isinstance(widget,QWidget) and widget.isWindow():
            self.shown.append(type(widget).__name__)
        return False
watch=Watch();app.installEventFilter(watch)
for row in rows:
    scheduler.result_ready.emit(row.platform,row)
app.processEvents()
assert not watch.shown, watch.shown
assert not dashboard.isVisible()
print('Overview data, filters, card reuse, refresh state, preference navigation and silent hidden updates passed')
