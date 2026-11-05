"""Native taskbar layout built from the floating board's quota markup."""
from html.parser import HTMLParser
from html import escape
import re
from .typography import typography,WEIGHTS,script_runs

class QuotaMarkup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.styles=[('#FF17202B','normal')]
    def handle_starttag(self,tag,attrs):
        if tag not in ('span','b'):return
        color,weight=self.styles[-1]
        style=dict(attrs).get('style','')
        for rule in style.split(';'):
            key,_,value=rule.partition(':')
            if key.strip()=='color':
                color=value.strip()
                if len(color)==7:color='#FF'+color[1:]
            if key.strip()=='font-weight' and value.strip() in ('600','700','bold','semibold'):weight='semibold'
        if tag=='b':weight='semibold'
        self.styles.append((color,weight))
    def handle_endtag(self,tag):
        if tag in ('span','b') and len(self.styles)>1:self.styles.pop()
    def handle_data(self,text):
        color,weight=self.styles[-1]
        for token in re.split(r'(\s+)',text):
            if not token:continue
            if token.isspace():
                # XAML trims trailing spaces when measuring individual text nodes.
                self.parts.append(dict(type='spacer',width=4*len(token),height=1))
            else:
                self.parts.append(dict(type='text',text=token,color=color,fontWeight=weight,fontSize=12,height=18,verticalAlignment='center'))

SUBTEXT_COLOR='#FF646A73'

def _text_pieces(markup,style,size,weight,height,family,cjk_family,color=None):
    """把一条 markup/纯文本拆成按中西文字体分段的原生文本片段。"""
    parser=QuotaMarkup();parser.feed(markup)
    pieces=[]
    for part in parser.parts:
        if part['type']=='spacer':
            part['width']=max(4,round(part['width']*size/12));pieces.append(part);continue
        for run,script in script_runs(part['text']):
            piece=dict(part,text=run,fontFamily=cjk_family if script=='cjk' else family,fontSize=size,fontWeight=weight,height=height)
            if color:piece['color']=color
            pieces.append(piece)
    return pieces

def make_rows_layout(rows,options=None,badge=None):
    """按窗口分行：rows=[{markup,reset}]。

    两行及以上：每行是「额度 + 该窗口的重置时间」；
    只有一行：额度在上、重置时间单独一行，余额类没有重置时只留额度行。
    """
    style=typography(options)
    name_height=style['name_size']+4;quota_height=style['quota_size']+4
    width=max(220,round(220*max(style['name_size']/12,style['quota_size']/12)))
    name_weight=WEIGHTS[style['weight']];quota_weight=WEIGHTS[style['quota_weight']]
    def quota_pieces(markup):
        return _text_pieces(markup,style,style['quota_size'],quota_weight,quota_height,style['quota_family'],style['quota_cjk_family'])
    def reset_pieces(text):
        return _text_pieces(escape(text),style,style['name_size'],name_weight,name_height,style['family'],style['cjk_family'],SUBTEXT_COLOR)
    def badge_pieces():
        from .deepseek_period import badge_style
        colors=badge_style(badge)
        return [dict(type='spacer',width=5,height=1),
                dict(type='card',backgroundColor=colors['background'],radius=3,
                     padding=dict(left=3,right=3,top=0,bottom=0),verticalAlignment='center',
                     children=[dict(type='text',text=badge,color=colors['text'],
                                    fontFamily=style['cjk_family'],fontSize=style['name_size'],
                                    fontWeight=name_weight,height=name_height,
                                    verticalAlignment='center')])]
    lines=[]
    if len(rows)<=1:
        row=rows[0] if rows else dict(markup='',reset='')
        lines.append(dict(type='row',gap=0,height=quota_height,horizontalAlignment='left',children=quota_pieces(row.get('markup',''))))
        sub=reset_pieces(row['reset']) if row.get('reset') else []
        if badge:sub+=badge_pieces()
        if sub:
            lines.append(dict(type='row',gap=0,height=name_height,horizontalAlignment='left',children=sub))
    else:
        for row in rows:
            pieces=quota_pieces(row.get('markup',''))
            if row.get('reset'):
                pieces.append(dict(type='spacer',width=6,height=1))
                pieces+=reset_pieces(row['reset'])
            lines.append(dict(type='row',gap=0,height=quota_height,horizontalAlignment='left',children=pieces))
        if badge:lines[-1]['children']+=badge_pieces()
    total=sum(line['height'] for line in lines)
    height=max(40,total+2);vertical_padding=max(1,(height-total)//2);row_height=height-2*vertical_padding
    return dict(type='card',width=width,height=height,backgroundColor='#00000000',padding=dict(left=6,right=8,top=vertical_padding,bottom=vertical_padding),radius=0,children=[
        dict(type='row',gap=8,height=row_height,verticalAlignment='center',horizontalAlignment='left',children=[
            dict(type='image',source=dict(bind='data.icon'),width=22,height=22,verticalAlignment='center',stretch='uniform',backgroundColor='#00000000'),
            dict(type='column',width=width-44,height=row_height,gap=0,verticalAlignment='center',horizontalAlignment='left',children=lines)])])

def make_layout(markup,options=None,sub_text=None,badge=None):
    """单窗口/余额的单行构造：额度一行，可选的重置时间单独一行。"""
    return make_rows_layout([dict(markup=markup,reset=sub_text or '')],options,badge)

def make_details(result):
    lines=[]
    if not result.ok:lines=['查询状态：暂时无法获取',result.error]
    elif result.metrics:
        for metric in result.metrics:
            try:percent=float(metric['percent'])
            except (KeyError,ValueError,TypeError):continue
            name={'5h':'5 小时剩余','周':'每周剩余'}.get(metric.get('label'),metric.get('label',''))
            lines.append(f'{name}：{percent:.0f}%')
            note=str(metric.get('note',''))
            import re
            note=re.sub(r'^(?:5h|周)\s*重置\s*','',note)
            if note:lines.append('重置时间：'+note)
    else:
        lines=['当前余额：'+result.display]
        from .balance_display import CURRENCIES
        precision=4 if result.unit in CURRENCIES else 2
        if result.total is not None:lines.append(f'总量：{result.total:,.{precision}f} {result.unit}')
        if result.used is not None:lines.append(f'已用：{result.used:,.{precision}f} {result.unit}')
        if result.sub_note:lines.append('说明：'+result.sub_note)
    if result.ok:
        lines.extend(str(item.get('label',''))+'：'+str(item.get('value','')) for item in (result.details or []))
    if result.platform=='deepseek':
        from .deepseek_period import pricing_period
        lines.append('计费时段：'+pricing_period())
    lines.append('刷新时间：'+result.updated_at)
    return [line for line in lines if line][:11]

def expanded_layout(line_count=11):
    children=[dict(type='text',bind='data.label',fontSize=16,fontWeight='semibold',color='#FF111111',horizontalAlignment='left')]
    children += [dict(type='text',bind=f'data.line{i}',fontSize=11,height=25,color='#FF222222',horizontalAlignment='left') for i in range(line_count)]
    return dict(type='card',width=360,height=detail_height(line_count),padding=16,radius=12,backgroundColor='#FFFFFFFF',children=[dict(type='column',gap=4,children=children)])

def detail_height(line_count):
    return max(140,min(460,64+29*line_count))
