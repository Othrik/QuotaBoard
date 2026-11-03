"""Shared typography for the floating board and native taskbar view.

字体分为两组，可分别设置：
- 名称（AI 名称，如 ChatGPT）：family / weight / name_size
- 额度（数字与百分比，如 5h 88%）：quota_family / quota_weight / quota_size

默认组合参考 Windows 11 任务栏天气小组件：小字用 Segoe UI Variable Text
常规字重，大号数字用 Segoe UI Variable Display 较粗字重，形成层级对比。
"""
FAMILIES=('Microsoft YaHei UI','Microsoft YaHei','DengXian',
          'Segoe UI Variable Text','Segoe UI Variable Text Semilight','Segoe UI Variable Text Semibold',
          'Segoe UI Variable Display','Segoe UI Variable Display Semilight','Segoe UI Variable Display Light','Segoe UI Variable Display Semibold',
          'Segoe UI Variable','Segoe UI')
WEIGHTS={400:'normal',600:'semibold',700:'bold'}
# 天气小组件风格：名称常规小字 + 额度 Display 较粗大数字
WEATHER_PRESET=dict(family='Segoe UI Variable Text',weight=400,name_size=12,
                    quota_family='Segoe UI Variable Display',quota_weight=600,quota_size=15)
def typography(value=None):
    value=value if isinstance(value,dict) else {}
    def number(key,default,low,high):
        try:return max(low,min(high,int(value.get(key,default))))
        except (TypeError,ValueError):return default
    def family(key,default):
        raw=value.get(key,default)
        return raw if raw in FAMILIES else default
    name_family=family('family','Microsoft YaHei UI')
    name_weight=number('weight',700,400,700)
    if name_weight not in WEIGHTS:name_weight=700
    quota_family=family('quota_family',name_family)
    quota_weight=number('quota_weight',name_weight,400,700)
    if quota_weight not in WEIGHTS:quota_weight=name_weight
    return dict(family=name_family,weight=name_weight,name_size=number('name_size',12,10,16),
                quota_family=quota_family,quota_weight=quota_weight,quota_size=number('quota_size',12,10,18))
