from quotaboard.model import QuotaResult
from quotaboard.ui.floating_window import _dock_quota_text,_quota_details,C_RED
from quotaboard.taskbar_layout import QuotaMarkup

def parsed(markup):
 parser=QuotaMarkup();parser.feed(markup);return parser.parts
def plain(markup):return ''.join(part.get('text',' ') for part in parsed(markup))

def quota(h,w):
 return QuotaResult(platform='codex',label='ChatGPT',display='示意',metrics=[{'label':'5h','percent':h,'note':'5h重置 22:47'},{'label':'周','percent':w,'note':'周重置 11-07 20:01'}])
a=_dock_quota_text(quota(0,0));assert '11月7日 20:01 周重置' in plain(a) and C_RED in a and '5h' not in a
b=_dock_quota_text(quota(0,90));assert '5h 22:47重置' in plain(b) and '90%' in b
for text in (a,b,_dock_quota_text(quota(0,0),reset_mode='countdown')):
 assert all(part['color']=='#FF111111' for part in parsed(text) if part.get('text') in ('5h','周'))
assert any(part.get('text')=='22:47重置' and part['color']=='#FF'+C_RED[1:] for part in parsed(b))
c=_dock_quota_text(quota(66,90));assert '66%' in c and '重置' not in c
r=QuotaResult(platform='dmxapi',label='DMXAPI',display='¥12.3456',updated_at='2026-11-02 10:00:00')
assert '¥12.3456' in _quota_details(r) and '10:00:00' in _quota_details(r)
print('Exhaustion priority, reset text and detailed hover passed')
