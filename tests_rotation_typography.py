from PySide6.QtCore import QCoreApplication
from quotaboard.taskbar import rotation_candidates
from quotaboard.taskbar_layout import make_layout
from quotaboard.typography import typography
from quotaboard.scheduler import Scheduler
from quotaboard.model import QuotaResult
app=QCoreApplication.instance() or QCoreApplication([])
good=QuotaResult(platform='codex',label='ChatGPT',display='0%',percent=0)
failed=QuotaResult(platform='gemini',label='Gemini',display='请求失败',ok=False)
assert rotation_candidates([good,failed])==[good], 'Exhausted but successful quota must remain visible'
failed.ok=True;assert rotation_candidates([good,failed])==[good,failed]
failed.ok=False
class Config:
 def set_cache(self,*args):pass
 def save(self):pass
scheduler=Scheduler(Config());scheduler.running=True;scheduler.expected=2;partial=[]
scheduler.result_ready.connect(lambda key,result:partial.append((key,result.ok)))
scheduler._on_done('gemini',failed);assert partial==[('gemini',False)] and scheduler.running
scheduler._on_done('codex',good);assert not scheduler.running
for options in [None,dict(family='DengXian',weight=400,name_size=14,quota_size=16)]:
 style=typography(options);layout=make_layout('5h <span style="color:#27AE80;font-weight:700">98%</span> · 周 29%',options)
 title=layout['children'][0]['children'][1]['children'][0]
 parts=layout['children'][0]['children'][1]['children'][1]['children']
 assert title['fontFamily']==style['family']
 assert 40<=layout['height']<=48
 for part in parts:
  if part['type']=='text':assert part['fontFamily']==style['family'] and part['fontWeight']==title['fontWeight']
assert typography({'family':'invalid','weight':None})['weight']==700
print('Failure exclusion/recovery, immediate per-provider updates, exhausted quotas and uniform font sizing passed')
