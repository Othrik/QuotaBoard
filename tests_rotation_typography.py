from PySide6.QtCore import QCoreApplication
from quotaboard.taskbar import rotation_candidates
from quotaboard.taskbar_layout import make_layout
from quotaboard.typography import WEIGHTS,typography
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
for options in [None,dict(family='DengXian',weight=400,name_size=14,quota_size=16),
                dict(family='Segoe UI Variable Text',weight=400,name_size=12,quota_family='Segoe UI Variable Display',quota_weight=600,quota_size=15)]:
 style=typography(options);layout=make_layout('5h <span style="color:#27AE80;font-weight:700">98%</span> · 周 29%',options)
 title=layout['children'][0]['children'][1]['children'][0]
 parts=layout['children'][0]['children'][1]['children'][1]['children']
 assert title['fontFamily']==style['family'] and title['fontWeight']==WEIGHTS[style['weight']]
 assert 40<=layout['height']<=48
 for part in parts:
  if part['type']=='text':assert part['fontFamily']==style['quota_family'] and part['fontWeight']==WEIGHTS[style['quota_weight']]
combined=typography(dict(family='Segoe UI Variable Text',weight=400,name_size=12,quota_family='Segoe UI Variable Display',quota_weight=600,quota_size=15))
assert combined['family']!=combined['quota_family'] and combined['weight']!=combined['quota_weight'],'Name and quota fonts must be adjustable independently'
assert typography({'family':'invalid','weight':None,'quota_family':'bogus'})['quota_family']=='Segoe UI Variable Text'
assert typography({'family':'invalid','weight':None})['weight']==600
default=typography(None)
assert (default['weight'],default['name_size'],default['quota_weight'],default['quota_size'])==(600,12,600,12),'默认应为较粗 12px'
assert default['family']=='Segoe UI Variable Text' and default['quota_family']=='Segoe UI Variable Display'
print('Failure exclusion/recovery, per-provider updates, exhausted quotas and split name/quota typography passed')
