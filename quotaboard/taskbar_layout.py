"""Native taskbar layout built from the floating board's quota markup."""
from html.parser import HTMLParser
import re
from .typography import typography,WEIGHTS

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

def make_layout(markup,options=None):
    parser=QuotaMarkup();parser.feed(markup);style=typography(options)
    name_height=style['name_size']+4;quota_height=style['quota_size']+4
    height=40;vertical_padding=max(1,(height-name_height-quota_height)//2);row_height=height-2*vertical_padding
    width=max(220,round(220*max(style['name_size']/12,style['quota_size']/12)))
    weight=WEIGHTS[style['weight']]
    for part in parser.parts:
        if part['type']=='text':part.update(fontFamily=style['family'],fontSize=style['quota_size'],fontWeight=weight,height=quota_height)
        else:part['width']=max(4,round(part['width']*style['quota_size']/12))
    title=dict(type='text',bind='data.label',fontFamily=style['family'],fontSize=style['name_size'],fontWeight=weight,height=name_height,color='#FF17202B',horizontalAlignment='left')
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
        if result.total is not None:lines.append(f'总量：{result.total:,.2f} {result.unit}')
        if result.used is not None:lines.append(f'已用：{result.used:,.2f} {result.unit}')
        if result.sub_note:lines.append('说明：'+result.sub_note)
    lines.append('刷新时间：'+result.updated_at)
    return [line for line in lines if line][:11]

def expanded_layout(line_count=11):
    children=[dict(type='text',bind='data.label',fontSize=16,fontWeight='semibold',color='#FF111111',horizontalAlignment='left')]
    children += [dict(type='text',bind=f'data.line{i}',fontSize=11,height=25,color='#FF222222',horizontalAlignment='left') for i in range(line_count)]
    return dict(type='card',width=360,height=detail_height(line_count),padding=16,radius=12,backgroundColor='#FFFFFFFF',children=[dict(type='column',gap=4,children=children)])

def detail_height(line_count):
    return max(140,min(460,64+29*line_count))
