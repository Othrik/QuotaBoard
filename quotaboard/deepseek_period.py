"""DeepSeek billing periods, evaluated in Beijing time without an API request.

Rules: https://api-docs.deepseek.com/zh-cn/quick_start/pricing/
2026 calendar: https://www.gov.cn/zhengce/content/202511/content_7047090.htm
Unknown holiday years never silently assert peak pricing on a weekday.
"""
from datetime import datetime, timedelta, timezone, date

BEIJING=timezone(timedelta(hours=8))
RULE='北京时间周一至周五（不含中国法定节假日）09:00–12:00、14:00–18:00 为高峰，其余为空闲；空闲价为高峰价的一半。'
HOLIDAYS={2026:((1,1,1,3),(2,15,2,23),(4,4,4,6),(5,1,5,5),
                (6,19,6,21),(9,25,9,27),(10,1,10,7))}

def pricing_period(now=None):
    now=now or datetime.now(timezone.utc)
    now=now.replace(tzinfo=BEIJING) if now.tzinfo is None else now.astimezone(BEIJING)
    minutes=now.hour*60+now.minute
    if now.weekday()>=5 or not (540<=minutes<720 or 840<=minutes<1080):return '空闲'
    ranges=HOLIDAYS.get(now.year)
    if ranges is None:return '时段待确认'
    if any(date(now.year,a,b)<=now.date()<=date(now.year,c,d) for a,b,c,d in ranges):return '空闲'
    return '高峰'

def display_name(label,platform,now=None):
    return label+(' · '+pricing_period(now) if platform=='deepseek' else '')

# 时段徽标配色：彩色文字 + 浅色强调背景（ARGB，前两位为不透明度）。
PERIOD_BADGES={
    '高峰':{'text':'#FFDC2626','background':'#FFFEE2E2'},
    '空闲':{'text':'#FF16A34A','background':'#FFDCFCE7'},
    '时段待确认':{'text':'#FF64748B','background':'#FFF1F5F9'},
}

def split_period_label(label,platform):
    """拆出计费时段后缀，返回 (基础名称, 时段徽标文本或 None)。"""
    if platform!='deepseek':
        return label,None
    for badge in PERIOD_BADGES:
        suffix=' · '+badge
        if label.endswith(suffix):
            return label[:-len(suffix)],badge
    return label,None
