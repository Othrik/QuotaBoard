"""Independent surface profiles with explicit Chinese/western glyph fonts.

Legacy family/quota_family keys remain the western fonts for compatibility.
Chinese fonts are stored separately; floating names, quotas and notes also have
their own sizes and weights. Legacy floating appearance migrates on first save.
"""
FAMILIES=('Microsoft YaHei UI','Microsoft YaHei','DengXian',
          'Segoe UI Variable Text','Segoe UI Variable Text Semilight','Segoe UI Variable Text Semibold',
          'Segoe UI Variable Display','Segoe UI Variable Display Semilight','Segoe UI Variable Display Light','Segoe UI Variable Display Semibold',
          'Segoe UI Variable','Segoe UI','Arial','Calibri','Consolas','Times New Roman',
          'SimSun','SimHei','KaiTi','FangSong')
WEIGHTS={400:'normal',600:'semibold',700:'bold'}
# 恢复默认：名称 Text / 额度 Display，两组同为较粗、12px
DEFAULT_PRESET=dict(family='Segoe UI Variable Text',weight=600,name_size=12,
                    quota_family='Segoe UI Variable Display',quota_weight=600,quota_size=12,
                    cjk_family='Microsoft YaHei UI',quota_cjk_family='Microsoft YaHei UI',
                    note_family='Segoe UI',note_cjk_family='Microsoft YaHei UI',note_weight=400,note_size=11)
DEFAULT_FLOATING_PRESET={**DEFAULT_PRESET,'name_size':14,'quota_size':14}
WEATHER_PRESET=DEFAULT_PRESET
def typography(value=None, floating=False):
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
    note_weight=number('note_weight',400,400,700)
    return dict(family=name_family,weight=name_weight,name_size=number('name_size',DEFAULT_PRESET['name_size'],10,24 if floating else 16),
                quota_family=quota_family,quota_weight=quota_weight,quota_size=number('quota_size',DEFAULT_PRESET['quota_size'],10,24 if floating else 18),
                cjk_family=family('cjk_family','Microsoft YaHei UI'),quota_cjk_family=family('quota_cjk_family','Microsoft YaHei UI'),
                note_family=family('note_family',quota_family),note_cjk_family=family('note_cjk_family','Microsoft YaHei UI'),
                note_weight=note_weight if note_weight in WEIGHTS else 400,note_size=number('note_size',11,9,18))

def floating_typography(data):
    value=data.get('floating_typography')
    if not isinstance(value,dict):
        previous=typography(data.get('display_typography'))
        value={**previous,'name_size':previous['name_size']+2,'quota_size':previous['quota_size']+2}
    return typography(value,floating=True)

def script_runs(text):
    """Preserve the text exactly while splitting CJK and western glyph runs."""
    runs=[]
    for ch in str(text):
        script='cjk' if ord(ch)>=0x2E80 else 'latin'
        if runs and runs[-1][1]==script:runs[-1]=(runs[-1][0]+ch,script)
        else:runs.append((ch,script))
    return runs

def role_values(style,role):
    prefix='' if role=='name' else role+'_'
    return (style[prefix+'family'],style['cjk_family' if role=='name' else prefix+'cjk_family'],
            style['name_size' if role=='name' else prefix+'size'],style['weight' if role=='name' else prefix+'weight'])

def mixed_text(text,style,role='name',font_only=False):
    from html import escape
    latin,cjk,size,weight=role_values(style,role)
    output=[]
    for run,script in script_runs(text):
        family=cjk if script=='cjk' else latin
        css=f"font-family:'{escape(family,quote=True)}';"
        if not font_only:css+=f'font-size:{size}px;font-weight:{weight};'
        output.append(f'<span style="{css}">{escape(run)}</span>')
    return ''.join(output)

def restyle_markup(markup,style,role='quota',font_only=False):
    from html.parser import HTMLParser
    class Painter(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
        def handle_starttag(self,tag,attrs):self.parts.append(self.get_starttag_text())
        def handle_startendtag(self,tag,attrs):self.parts.append(self.get_starttag_text())
        def handle_endtag(self,tag):self.parts.append(f'</{tag}>')
        def handle_data(self,text):self.parts.append(mixed_text(text,style,role,font_only))
    painter=Painter();painter.feed(markup);return ''.join(painter.parts)
