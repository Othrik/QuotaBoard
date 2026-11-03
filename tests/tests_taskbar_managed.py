"""Verify the integrated helper contract without touching the Windows taskbar."""
from pathlib import Path
import json,tempfile,time
from PySide6.QtCore import QCoreApplication,QObject,QProcess
from quotaboard.taskbar import TaskbarController
from quotaboard.taskbar_layout import make_layout,make_details,expanded_layout
from quotaboard.ui.floating_window import _dock_quota_text
from quotaboard.model import QuotaResult

app=QCoreApplication.instance() or QCoreApplication([])
case=QuotaResult(platform='gemini',label='Gemini',display='5h 94% · 周 29%',metrics=[dict(label='5h',percent=94,note='5h重置 03:05'),dict(label='周',percent=29,note='周重置 11-07 20:01')])
layout=make_layout(_dock_quota_text(case));parts=layout['children'][0]['children'][1]['children'][1]['children']
assert ''.join(p.get('text',' ') for p in parts)=='5h 94% · 周 29%'
assert any(p.get('text')=='94%' and p['color']=='#FF27AE80' for p in parts)
assert any(p.get('text')=='29%' and p['color']=='#FFE45D6A' for p in parts)
assert layout['backgroundColor']=='#00000000'
assert layout['padding']['left']==6
for label in ['5h','周']:
 index=next(i for i,p in enumerate(parts) if p.get('text')==label)
 assert parts[index+1]['type']=='spacer' and parts[index+1]['width']>=4
details=make_details(case)
assert len(expanded_layout(len(details))['children'][0]['children'])==len(details)+1
case.metrics[1]['percent']=0
layout=make_layout(_dock_quota_text(case));parts=layout['children'][0]['children'][1]['children'][1]['children']
assert ''.join(p.get('text',' ') for p in parts)=='11月7日 20:01 周重置'
assert parts[0]['color']=='#FFE45D6A' and parts[0]['fontWeight']=='semibold'
assert '重置时间：11-07 20:01' in make_details(case)

class Process:
 def __init__(self):self.running=False;self.starts=0
 def state(self):return QProcess.Running if self.running else QProcess.NotRunning
 def setProgram(self,p):self.program=p
 def setArguments(self,a):self.args=a
 def setWorkingDirectory(self,p):pass
 def start(self):self.starts+=1;self.running=True
 def waitForStarted(self,n):return True
 def waitForFinished(self,n):self.running=False;return True
 def kill(self):self.running=False
class Config:
 def __init__(self,p):self.path=p;self._data={'taskbar_mode':True}
 def save(self):pass
if True:
 tmp=Path('dist/managed-test');tmp.mkdir(parents=True,exist_ok=True)
 owner=QObject();controller=TaskbarController(Config(Path(tmp)/'config.json'),owner);controller.timer.stop();controller.command_timer.stop();controller.prepared=True;controller.process=Process();errors=[];controller.failed.connect(errors.append);controller.set_rows([case]);controller.tick()
 state_path=controller.data/'State/com.othrik.quotaboard.json'
 unchanged_time=state_path.stat().st_mtime_ns;controller.tick()
 assert state_path.stat().st_mtime_ns==unchanged_time,'Unchanged quota rebuilt the native anchor'
 assert controller.process.starts==1,errors
 assert controller.process.args[0]=='--quotaboard-parent'
 catalog=json.loads((controller.data/'Runtime/WidgetCatalog.json').read_text('utf8'))
 state=json.loads((controller.data/'State/com.othrik.quotaboard.json').read_text('utf8'))
 assert catalog['widgets'][0]['renderer']=='native' and state['data']['label']=='Gemini'
 assert '缓存' not in state['data']['label']
 assert all(word not in json.dumps(state) for word in ['api_key','cookie','credential'])
 opened=[]
 def reenter_settings():
  opened.append(True);controller.read_commands()
 controller.settings_requested.connect(reenter_settings)
 commands=controller.data/'Commands';commands.mkdir(exist_ok=True)
 (commands/'settings.json').write_text(json.dumps(dict(action='openSettings',widgetId='com.othrik.quotaboard',createdAtUnix=time.time())),encoding='utf8')
 controller.read_commands();assert opened==[True] and not list(commands.glob('*.json'))
 (commands/'position.json').write_text(json.dumps(dict(action='moveWidget',widgetId='com.othrik.quotaboard',createdAtUnix=time.time(),positionPct=25,offsetPx=12)),encoding='utf8')
 controller.read_commands();controller.tick()
 assert json.loads((controller.data/'config.json').read_text('utf8'))['widgets'][0]['position']==dict(anchorPercent=25,offsetPx=12)
 shown=[];controller.details_requested.connect(shown.append)
 (commands/'details.json').write_text(json.dumps(dict(action='showQuotaDetails',widgetId='com.othrik.quotaboard',createdAtUnix=time.time(),platform='gemini')),encoding='utf8')
 controller.read_commands();assert shown==['gemini']
 failed=QuotaResult(platform='gemini',label='Gemini',display='请求失败',ok=False)
 controller.set_rows([failed]);assert not json.loads((controller.data/'config.json').read_text('utf8'))['widgets'][0]['enabled']
 controller.set_rows([case]);assert json.loads((controller.data/'config.json').read_text('utf8'))['widgets'][0]['enabled']
 controller.config._data['platforms']={'gemini':{'taskbar_enabled':False}}
 controller.tick()
 assert controller.rows==[case], 'excluded platforms must remain available to the overview'
 assert not json.loads((controller.data/'config.json').read_text('utf8'))['widgets'][0]['enabled']
 controller.config._data['platforms']['gemini']['taskbar_enabled']=True
 controller.tick()
 assert json.loads((controller.data/'config.json').read_text('utf8'))['widgets'][0]['enabled']
 controller.config._data['taskbar_mode']=False;controller.tick();assert not json.loads((controller.data/'managed-control.json').read_text('utf8'))['enabled']
 assert controller.process.state()==QProcess.NotRunning
print('Integrated layout parity, transparency, helper single-start, data boundary and shutdown passed')
