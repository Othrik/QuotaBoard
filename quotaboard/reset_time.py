"""Local countdowns from provider reset timestamps, without polling the API."""
from datetime import datetime,timedelta
import math
import re
import time


def reset_timestamp(result,metric):
    raw=metric.get('resets_at')
    try:
        value=float(raw) if not isinstance(raw,bool) else 0
        if math.isfinite(value) and 0<value<4102444800:
            return value
    except (TypeError,ValueError,OverflowError):
        pass
    # Legacy cache has formatted clocks only. Anchor to its fetch date, never
    # today's date, so an expired cache cannot silently become tomorrow's reset.
    try:
        captured=datetime.fromisoformat(result.updated_at)
    except (ValueError,TypeError):
        return None
    label=str(metric.get('label',''))
    note=str(metric.get('note',''))+' '+result.sub_note
    if label=='5h':
        match=re.search(r'5h\s*重置\s*(\d{1,2}):(\d{2})',note,re.I)
        if not match:return None
        try:
            target=captured.replace(hour=int(match[1]),minute=int(match[2]),second=0,microsecond=0)
            if (captured-target).total_seconds()>12*3600:target+=timedelta(days=1)
            return target.timestamp()
        except ValueError:return None
    if label=='周':
        match=re.search(r'周\s*重置\s*(?:(\d{4})-)?(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})',note)
        if not match:return None
        years=[int(match[1])] if match[1] else [captured.year-1,captured.year,captured.year+1]
        candidates=[]
        for year in years:
            try:candidates.append(captured.replace(year=year,month=int(match[2]),day=int(match[3]),hour=int(match[4]),minute=int(match[5]),second=0,microsecond=0))
            except ValueError:continue
        if match[1]:return candidates[0].timestamp() if candidates else None
        upcoming=[target for target in candidates if -120<=(target-captured).total_seconds()<=14*86400]
        if upcoming:return min(upcoming).timestamp()
        same_year=next((target for target in candidates if target.year==captured.year),None)
        return same_year.timestamp() if same_year else None
    return None


def countdown_text(result,metric,now=None):
    target=reset_timestamp(result,metric)
    if target is None:return None
    seconds=target-(time.time() if now is None else now)
    if seconds<=0:return '等待刷新'
    minutes=math.ceil(seconds/60)
    days,remaining=divmod(minutes,1440)
    hours,minutes=divmod(remaining,60)
    pieces=[]
    if days:pieces.append(f'{days}天')
    if hours:pieces.append(f'{hours}小时')
    if minutes:pieces.append(f'{minutes}分' if days or hours else f'{minutes}分钟')
    return ''.join(pieces)+'后重置'
