"""任务栏两行：第一行余量、第二行重置时间，平台名不再占一行。"""
import json
from quotaboard.model import QuotaResult
from quotaboard.taskbar import taskbar_quota_text,taskbar_reset_text
from quotaboard.taskbar_layout import make_layout

case=QuotaResult('gemini','Gemini','5h 94% · 周 29%',metrics=[dict(label='5h',percent=94,note='5h重置 03:05'),dict(label='周',percent=29,note='周重置 11-07 20:01')])
reset=taskbar_reset_text(case)
assert reset=='5h 03:05 · 周 11-07 20:01',reset
layout=make_layout(taskbar_quota_text(case),None,reset)
column=layout['children'][0]['children'][1]
top,bottom=column['children'][0],column['children'][1]
top_text=''.join(p.get('text',' ') for p in top['children'])
bottom_text=''.join(p.get('text',' ') for p in bottom['children'])
assert top_text=='5h 94% · 周 29%',top_text
assert bottom_text==reset,bottom_text
assert all(p['color']=='#FF646A73' for p in bottom['children'] if p.get('type')=='text')
assert 'Gemini' not in json.dumps(layout,ensure_ascii=False),'平台名不应再出现在任务栏两行里'
balance=QuotaResult('deepseek','DeepSeek开放平台','¥18.24')
assert taskbar_reset_text(balance)=='','余额类平台没有重置时间时第二行留空'
single=make_layout(taskbar_quota_text(balance),None,'')
assert len(single['children'][0]['children'][1]['children'])==1,'没有重置时间时只保留一行，避免空白第二行'
assert ''.join(p.get('text',' ') for p in single['children'][0]['children'][1]['children'][0]['children'])=='余额 ¥18.24'
countdown=taskbar_reset_text(case,reset_mode='countdown')
assert countdown.startswith('5h ') and '后' in countdown and '重置' not in countdown,countdown
from datetime import datetime
stamp=datetime(2026,11,6,9,30).timestamp()
only_ts=QuotaResult('gemini','Gemini','5h 40%',metrics=[dict(label='5h',percent=40,resets_at=stamp)])
assert taskbar_reset_text(only_ts)=='5h 09:30',taskbar_reset_text(only_ts)
assert taskbar_reset_text(QuotaResult('gemini','Gemini','—',ok=False))==''
print('Taskbar two-line layout: quota first, reset time second, no platform name passed')
