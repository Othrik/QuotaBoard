from datetime import datetime,timezone
from quotaboard.deepseek_period import pricing_period,display_name
from quotaboard.model import QuotaResult
from quotaboard.taskbar import taskbar_label,taskbar_quota_text
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
assert _dock_quota_text(row,now=datetime(2026,11,5,10)).endswith(' · 高峰')
assert _dock_quota_text(row,now=datetime(2026,11,5,18)).endswith(' · 空闲')
print('DeepSeek Beijing-time boundaries, holidays, weekends, timezone and display labels passed')
