"""Shared typography for the floating board and native taskbar view."""
FAMILIES=('Microsoft YaHei UI','Microsoft YaHei','DengXian')
WEIGHTS={400:'normal',600:'semibold',700:'bold'}
def typography(value=None):
    value=value if isinstance(value,dict) else {}
    def number(key,default,low,high):
        try:return max(low,min(high,int(value.get(key,default))))
        except (TypeError,ValueError):return default
    family=value.get('family','Microsoft YaHei UI');weight=number('weight',700,400,700)
    return dict(family=family if family in FAMILIES else FAMILIES[0],weight=weight if weight in WEIGHTS else 700,name_size=number('name_size',12,10,14),quota_size=number('quota_size',12,10,16))
