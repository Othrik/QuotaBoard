"""任务栏按窗口分行：5h 一行「额度+重置」，周 一行「额度+重置」；单窗口时额度在上、重置在下。"""
from datetime import datetime
import time
from quotaboard.model import QuotaResult
from quotaboard.taskbar import taskbar_quota_text,taskbar_window_rows,taskbar_refresh_text
from quotaboard.taskbar_layout import make_layout,make_rows_layout

def lines(layout):
    column=layout['children'][0]['children'][1]
    return [''.join(p.get('text',' ') for p in row['children']) for row in column['children']]

dual=QuotaResult('gemini','Gemini','5h 94% · 周 29%',updated_at='2026-11-06 00:30:00',metrics=[
    dict(label='5h',percent=94,note='5h重置 03:05'),
    dict(label='周',percent=29,note='周重置 11-07 20:01')])
rows=taskbar_window_rows(dual)
assert [r['reset'] for r in rows]==['03:05重置','11-07 20:01重置'],rows
layout=make_rows_layout(rows)
assert lines(layout)==['5h 94% 03:05重置','周 29% 11-07 20:01重置'],lines(layout)
texts=[p.get('text') for row in layout['children'][0]['children'][1]['children'] for p in row['children'] if p.get('text')]
assert 'Gemini' not in texts,'平台名不应再出现在任务栏里'
row1=[p for p in layout['children'][0]['children'][1]['children'][0]['children'] if p.get('type')=='text']
assert any(p['text']=='94%' and p['color']=='#FF27AE80' for p in row1)
assert all(p['color']=='#FF17202B' for p in row1 if p['text']=='5h'),'窗口标签固定深色，不跟着额度变色'
assert all(p['color']=='#FF646A73' for p in row1 if p['text'].startswith('03:05'))
row2=[p for p in layout['children'][0]['children'][1]['children'][1]['children'] if p.get('type')=='text']
assert any(p['text']=='29%' and p['color']=='#FFE45D6A' for p in row2)
assert all(p['color']=='#FF17202B' for p in row2 if p['text']=='周')

weekly=QuotaResult('gemini','Gemini','周 29%',metrics=[dict(label='周',percent=29,note='周重置 11-07 20:01')])
assert len(taskbar_window_rows(weekly))==1
assert lines(make_rows_layout(taskbar_window_rows(weekly)))==['周 29%','11-07 20:01重置']

exhausted=QuotaResult('gemini','Gemini','周 0%',metrics=[dict(label='周',percent=0,note='周重置 11-07 20:01')])
ex_lines=lines(make_rows_layout(taskbar_window_rows(exhausted)))
assert ex_lines==['周 0%','11-07 20:01重置'],ex_lines
ex_first=[p for p in make_rows_layout(taskbar_window_rows(exhausted))['children'][0]['children'][1]['children'][0]['children'] if p.get('type')=='text']
assert any(p['text']=='0%' and p['color']=='#FFE45D6A' for p in ex_first)

balance=QuotaResult('deepseek','DeepSeek开放平台','¥18.24',updated_at='2026-11-06 06:10:51')
assert taskbar_window_rows(balance)==[],'余额类没有窗口'
assert taskbar_refresh_text(balance)=='06:10 刷新'
assert lines(make_layout(taskbar_quota_text(balance),None,taskbar_refresh_text(balance)))==['余额 ¥18.24','06:10 刷新']

assert taskbar_window_rows(dual,reset_mode='countdown')[1]['reset'].endswith('重置')
stamped=QuotaResult('gemini','Gemini','5h 94% · 周 29%',metrics=[
    dict(label='5h',percent=94,resets_at=time.time()+5*3600),
    dict(label='周',percent=29,resets_at=time.time()+3*86400)])
stamped_cd=[r['reset'] for r in taskbar_window_rows(stamped,reset_mode='countdown')]
assert stamped_cd[0].startswith('5小时') and stamped_cd[1].startswith('3天'),stamped_cd

stamp=datetime(2026,11,6,9,30).timestamp()
only_ts=QuotaResult('gemini','Gemini','5h 40%',metrics=[dict(label='5h',percent=40,resets_at=stamp)])
assert taskbar_window_rows(only_ts)[0]['reset']=='09:30重置'
failed=QuotaResult('gemini','Gemini','—',ok=False)
assert taskbar_window_rows(failed)==[] and taskbar_refresh_text(failed)==''

big=make_rows_layout(rows,dict(name_size=16,quota_size=18))
assert big['height']<=48,'宿主任务栏组件最大高度 48px'
print('Taskbar per-window rows: 5h quota+reset, weekly quota+reset, single-window fallback, balance refresh line passed')
