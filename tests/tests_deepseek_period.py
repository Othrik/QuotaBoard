from datetime import datetime,timezone
from quotaboard.deepseek_period import pricing_period,display_name,split_period_label,PERIOD_BADGES,badge_style
from quotaboard.model import QuotaResult
from quotaboard.taskbar import taskbar_label,taskbar_quota_text
from quotaboard.taskbar_layout import make_layout
from quotaboard.ui.floating_window import _dock_quota_text

for clock,expected in [('08:59','空闲'),('09:00','高峰'),('11:59','高峰'),
                       ('12:00','空闲'),('13:59','空闲'),('14:00','高峰'),
                       ('17:59','高峰'),('18:00','空闲')]:
    assert pricing_period(datetime.fromisoformat('2026-11-05T'+clock))==expected
assert pricing_period(datetime(2026,11,5,1,tzinfo=timezone.utc))=='高峰'
for day in ('2026-10-01','2026-02-23','2026-05-05','2026-09-25',
            '2026-05-09','2026-11-07','2026-11-08'):
    assert pricing_period(datetime.fromisoformat(day+'T10:00'))=='空闲'
assert pricing_period(datetime(2027,1,4,10))=='时段待确认'
assert pricing_period(datetime(2027,1,4,18))=='空闲'
assert display_name('ChatGPT','codex',datetime(2026,11,5,10))=='ChatGPT'
row=QuotaResult('deepseek','DeepSeek开放平台','¥18.24')
assert taskbar_label(row).startswith('DeepSeek开放平台 · ')
assert taskbar_quota_text(row)=='余额 ¥18.24'
peak_text=_dock_quota_text(row,now=datetime(2026,11,5,10))
off_text=_dock_quota_text(row,now=datetime(2026,11,5,18))
assert peak_text.endswith('高峰</span>') and 'color:#9F2923' in peak_text and 'background-color:#FFECEB' in peak_text
assert off_text.endswith('空闲</span>') and 'color:#293B37' in off_text and 'background-color:#E8F6F0' in off_text
assert '●' not in peak_text+off_text
base,badge=split_period_label(taskbar_label(row),'deepseek')
assert base=='DeepSeek开放平台' and badge in ('高峰','空闲','时段待确认')
assert split_period_label('Gemini · Pro','gemini')==('Gemini · Pro',None)
assert split_period_label('DeepSeek开放平台 · 高峰 · Plus','deepseek')==('DeepSeek开放平台 · 高峰 · Plus',None)
layout=make_layout(taskbar_quota_text(row),None,'',badge=badge)
secondary_row=layout['children'][0]['children'][1]['children'][1]
badge_parts=[p for p in secondary_row['children'] if p.get('type')=='card']
assert len(badge_parts)==1
badge_part=badge_parts[0]
assert badge_part['children'][0]['text']==badge
assert badge_part['backgroundColor']==PERIOD_BADGES[badge]['background']
assert badge_part['children'][0]['color']==PERIOD_BADGES[badge]['text']
assert badge_part['children'][0]['fontSize']==12
assert badge_part['radius']==3 and badge_part['padding']['left']==3
assert badge_style('高峰')['background_css'].startswith('rgba(')
assert not any(p.get('type')=='card' for p in make_layout('80%',None,'Gemini')['children'][0]['children'][1]['children'][1]['children'])
print('DeepSeek Beijing-time boundaries, holidays, weekends, timezone, badge styling and display labels passed')
