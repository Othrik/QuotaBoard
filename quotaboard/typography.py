"""Shared typography for the floating board and native taskbar view.

字体分为两组，可分别设置：
- 名称（AI 名称，如 ChatGPT）：family / weight / name_size
- 额度（数字与百分比，如 5h 88%）：quota_family / quota_weight / quota_size

默认组合参考 Windows 11 任务栏天气小组件：名称用 Segoe UI Variable Text、
额度用 Segoe UI Variable Display，两组都用较粗字重与 12px 字号。
"""
FAMILIES=('Microsoft YaHei UI','Microsoft YaHei','DengXian',
          'Segoe UI Variable Text','Segoe UI Variable Text Semilight','Segoe UI Variable Text Semibold',
          'Segoe UI Variable Display','Segoe UI Variable Display Semilight','Segoe UI Variable Display Light','Segoe UI Variable Display Semibold',
          'Segoe UI Variable','Segoe UI')
WEIGHTS={400:'normal',600:'semibold',700:'bold'}
# 恢复默认：名称 Text / 额度 Display，两组同为较粗、12px
DEFAULT_PRESET=dict(family='Segoe UI Variable Text',weight=600,name_size=12,
                    quota_family='Segoe UI Variable Display',quota_weight=600,quota_size=12)
WEATHER_PRESET=DEFAULT_PRESET
def typography(value=None):
    value=value if isinstance(value,dict) else {}
    def number(key,default,low,high):
        try:return max(low,min(high,int(value.get(key,default))))
        except (TypeError,ValueError):return default
    def family(key,default):
        raw=value.get(key,default)
        return raw if raw in FAMILIES else default
    name_family=family('family',DEFAULT_PRESET['family'])
    name_weight=number('weight',DEFAULT_PRESET['weight'],400,700)
    if name_weight not in WEIGHTS:name_weight=DEFAULT_PRESET['weight']
    # 用户只设置了名称组时，额度组跟随名称组；完全没配置时用默认的 Display 组
    quota_default_family=name_family if value.get('family') else DEFAULT_PRESET['quota_family']
    quota_default_weight=name_weight if value.get('weight') else DEFAULT_PRESET['quota_weight']
    quota_family=family('quota_family',quota_default_family)
    quota_weight=number('quota_weight',quota_default_weight,400,700)
    if quota_weight not in WEIGHTS:quota_weight=quota_default_weight
    return dict(family=name_family,weight=name_weight,name_size=number('name_size',DEFAULT_PRESET['name_size'],10,16),
                quota_family=quota_family,quota_weight=quota_weight,quota_size=number('quota_size',DEFAULT_PRESET['quota_size'],10,18))
