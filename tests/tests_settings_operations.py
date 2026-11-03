"""Exercise settings operations with fake credentials and a fake connection."""
import os,time,threading
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import Qt,QTimer
from quotaboard.config import Config
from quotaboard.model import QuotaResult
from quotaboard.ui.settings_dialog import SettingsDialog,PROVIDERS
app=QApplication.instance() or QApplication([])
class FakeConfig(Config):
 def __init__(self):
  super().__init__(Path('dist/settings-test/config-never-read.json'));self.saved=0;self.credentials={('deepseek','api_key'):'saved-test-key'}
 def get_credential(self,k,f):return self.credentials.get((k,f),'')
 def set_credential(self,k,f,v):self.credentials[k,f]=v
 def save(self):self.saved+=1
c=FakeConfig();d=SettingsDialog(c)
assert d.navigation.currentRow()==0 and d.pages.currentIndex()==0
assert d.field_inputs['deepseek']['api_key'].text()==''
d.order_list.setCurrentRow(0);first=d.order_list.item(0).data(256);d._move_order(1);assert d.order_list.item(1).data(256)==first
d._anchor_percent=50;d.position_spin.setValue(20);d._reset_position();assert d.position_spin.value()==0 and d._anchor_percent==0
release=threading.Event()
class Provider:
 def __init__(self,cfg):assert cfg['api_key']=='saved-test-key'
 def fetch(self):
  release.wait(2);return QuotaResult(platform='deepseek',label='DeepSeek',display='¥12.34')
original=PROVIDERS['deepseek'];PROVIDERS['deepseek']=Provider
try:
 ticks=[];timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:ticks.append(True));timer.start()
 d._test('deepseek');assert not d.test_buttons['deepseek'].isEnabled()
 deadline=time.monotonic()+0.15
 while time.monotonic()<deadline:app.processEvents();time.sleep(.005)
 assert ticks,'Connection test blocked UI events'
 release.set();deadline=time.monotonic()+3
 while d._workers and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
 assert not d._workers and '连接成功' in d.test_status['deepseek'].text()
 assert c.saved==0,'Connection test unexpectedly saved settings'
 d.font_weight.setCurrentIndex(d.font_weight.findData(700));d.name_size.setValue(13);d.quota_size.setValue(14)
 d.quota_family.setCurrentIndex(d.quota_family.findData('Segoe UI Variable Display'));d.quota_weight.setCurrentIndex(d.quota_weight.findData(600))
 saved=[]
 d.saved.connect(lambda: saved.append(True))
 d._save();assert c.saved==1 and saved,'Save must emit the saved signal for immediate refresh'
 assert d.result()==0 and '已保存' in d.save_status.text(),'Save must keep the panel open'
 assert not (d.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),'Settings must not force topmost'
 assert c.get_credential('deepseek','api_key')=='saved-test-key'
 assert c._data['taskbar_position']==dict(anchorPercent=0,offsetPx=0)
 assert c.platform_order[1]==first
 assert c._data['display_typography']['weight']==700 and c._data['display_typography']['quota_size']==14
 assert c._data['display_typography']['quota_family']=='Segoe UI Variable Display' and c._data['display_typography']['quota_weight']==600
finally:release.set();PROVIDERS['deepseek']=original
print('Settings navigation, sorting, reset position, secret preservation, async responsiveness and save passed')
