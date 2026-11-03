import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from datetime import datetime
from unittest.mock import patch,Mock
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument
from quotaboard.model import QuotaResult
from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.reset_time import countdown_text,reset_timestamp
from quotaboard.ui.floating_window import FloatingWindow,_dock_quota_text
from quotaboard.ui.settings_dialog import SettingsDialog
from quotaboard.providers.gemini_provider import GeminiProvider

def plain(markup):
    document=QTextDocument();document.setHtml(markup);return document.toPlainText()

now=datetime(2026,11,4,12).timestamp()
row=QuotaResult('codex','ChatGPT','5h 0% · 周 80%',updated_at='2026-11-04 12:00:00',metrics=[
    dict(label='5h',percent=0,resets_at=now+7200,note='5h重置 14:00'),dict(label='周',percent=80)])
assert countdown_text(row,row.metrics[0],now)=='2小时后重置'
assert countdown_text(row,row.metrics[0],now+3601)=='1小时后重置'
assert countdown_text(row,row.metrics[0],now+7190)=='1分钟后重置'
assert countdown_text(row,row.metrics[0],now+7200)=='等待刷新'
text=_dock_quota_text(row,reset_mode='countdown',now=now)
assert '5h 2小时后重置' in text and '80%' in text
assert '14:00' in _dock_quota_text(row), 'default mode must preserve absolute times'
row.metrics[1]=dict(label='周',percent=0,resets_at=now+86400+3*3600+5*60,note='周重置 11-05 15:05')
assert '周 1天3小时5分后重置' in _dock_quota_text(row,reset_mode='countdown',now=now)
assert '11月5日 15:05 周重置' in _dock_quota_text(row)
legacy=QuotaResult('codex','ChatGPT','0%',updated_at='2026-12-31 23:30:00')
metric=dict(label='5h',note='5h重置 00:30')
assert reset_timestamp(legacy,metric)==datetime(2027,1,1,0,30).timestamp()
week=dict(label='周',note='周重置 01-02 20:01')
assert reset_timestamp(legacy,week)==datetime(2027,1,2,20,1).timestamp()
assert countdown_text(legacy,metric,datetime(2027,1,2).timestamp())=='等待刷新'
assert countdown_text(legacy,dict(label='周',note='unknown'),now) is None
gemini=GeminiProvider({})
with patch.object(gemini,'_get_cookies',return_value={}),patch.object(gemini,'_query_with_recovery',return_value=[2,[[10,0.5,1,[[now+7200,0]]]],False]):
    queried=gemini.fetch()
assert queried.ok and queried.metrics[0]['resets_at']==now+7200
assert countdown_text(queried,queried.metrics[0],now)=='2小时后重置'

app=QApplication([])
config=Config(Path('dist/countdown-test/config.json'))
config._data['platforms']={'codex':{'enabled':True}}
config._data['reset_display']='countdown'
config.save=lambda:None
scheduler=Scheduler(config);scheduler.refresh_all=Mock()
row.metrics[1]=dict(label='周',percent=80)
window=FloatingWindow(config,scheduler)
window._dock_edge='top'
with patch('quotaboard.reset_time.time.time',return_value=now):
    window.on_results({'codex':row});app.processEvents();window.show();app.processEvents()
label=window._dock_value_labels[0][1]
assert '2小时后重置' in plain(label.text())
with patch('quotaboard.reset_time.time.time',return_value=now+3600):window._keep_taskbar_position()
assert window._dock_value_labels[0][1] is label
assert '1小时后重置' in plain(label.text())
scheduler.refresh_all.assert_not_called()
dialog=SettingsDialog(config)
assert dialog.reset_display.currentData()=='countdown'
dialog.reset_display.setCurrentIndex(dialog.reset_display.findData('absolute'));dialog._save()
assert config.get('reset_display')=='absolute'
window.hide();dialog.hide()
print('Countdown formatting, exhaustion priority, zero boundary, legacy/year rollover, live in-place update and saved mode passed')
