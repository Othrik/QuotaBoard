"""Native taskbar layout built from the floating board's quota markup."""
from html.parser import HTMLParser
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

def make_layout(markup,options=None,title_text=None,badge=None):
    parser=QuotaMarkup();parser.feed(markup);style=typography(options)
    name_height=style['name_size']+4;quota_height=style['quota_size']+4
    height=max(40,name_height+quota_height+2);vertical_padding=max(1,(height-name_height-quota_height)//2);row_height=height-2*vertical_padding
    width=max(220,round(220*max(style['name_size']/12,style['quota_size']/12)))
    name_weight=WEIGHTS[style['weight']]
    quota_weight=WEIGHTS[style['quota_weight']]
    parser.parts=[piece for part in parser.parts for piece in
                  ([dict(part,text=run,fontFamily=style['quota_cjk_family'] if script=='cjk' else style['quota_family']) for run,script in script_runs(part['text'])] if part['type']=='text' else [part])]
    for part in parser.parts:
        if part['type']=='text':part.update(fontSize=style['quota_size'],fontWeight=quota_weight,height=quota_height)
        else:part['width']=max(4,round(part['width']*style['quota_size']/12))
    title=dict(type='text',bind='data.label',fontFamily=style['family'],fontSize=style['name_size'],fontWeight=name_weight,height=name_height,color='#FF17202B',horizontalAlignment='left')
    if title_text is not None:
        from html import escape
        title_parser=QuotaMarkup();title_parser.feed(escape(title_text))
        pieces=[]
        for part in title_parser.parts:
            if part['type']=='spacer':pieces.append(part);continue
            for run,script in script_runs(part['text']):
                pieces.append(dict(part,text=run,fontFamily=style['cjk_family'] if script=='cjk' else style['family'],fontSize=style['name_size'],fontWeight=name_weight,height=name_height))
        if badge:
            from .deepseek_period import PERIOD_BADGES
            badge_style=PERIOD_BADGES.get(badge,PERIOD_BADGES['时段待确认'])
            pieces.append(dict(type='spacer',width=4,height=1))
            pieces.append(dict(type='card',backgroundColor=badge_style['background'],radius=6,
                               padding=dict(left=5,right=5,top=1,bottom=1),verticalAlignment='center',
                               children=[dict(type='text',text=badge,color=badge_style['text'],
                                              fontFamily=style['cjk_family'],fontSize=style['name_size'],
                                              fontWeight=name_weight,height=max(8,name_height-2),verticalAlignment='center')]))
        title=dict(type='row',gap=0,height=name_height,horizontalAlignment='left',children=pieces)
    values=dict(type='row',gap=0,height=quota_height,horizontalAlignment='left',children=parser.parts)
    return dict(type='card',width=width,height=height,backgroundColor='#00000000',padding=dict(left=6,right=8,top=vertical_padding,bottom=vertical_padding),radius=0,children=[dict(type='row',gap=8,height=row_height,verticalAlignment='center',horizontalAlignment='left',children=[dict(type='image',source=dict(bind='data.icon'),width=22,height=22,verticalAlignment='center',stretch='uniform',backgroundColor='#00000000'),dict(type='column',width=width-44,height=row_height,gap=0,verticalAlignment='center',horizontalAlignment='left',children=[title,values])])])

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
