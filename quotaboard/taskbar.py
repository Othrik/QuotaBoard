"""Own the bundled taskbar helper; no external app or extension installation."""
from __future__ import annotations
import hashlib,json,os,re,shutil,sys,time
from pathlib import Path
from PySide6.QtCore import QObject,QProcess,QTimer,Signal
from .model import QuotaResult,PLATFORM_META
from .taskbar_layout import make_layout,make_rows_layout,make_details,expanded_layout,detail_height
from . import __version__
from .balance_display import MONETARY_PLATFORMS
from .rotation import rotation_seconds
from .deepseek_period import split_period_label

WIDGET_ID='com.othrik.quotaboard'
LABEL_COLOR='#FF17202B'

def taskbar_label(result):
    plan = ' '.join(str(result.subscription_plan or '').split())
    label=PLATFORM_META.get(result.platform,{}).get('label',result.label)
    from .deepseek_period import display_name
    return display_name(label,result.platform) + (' · ' + plan[:24] if plan else '')

def taskbar_quota_text(result,reset_mode='absolute'):
    from .ui.floating_window import _dock_quota_text
    text=_dock_quota_text(result,reset_mode=reset_mode,show_period=False)
    if result.ok and result.platform in MONETARY_PLATFORMS and not result.display.startswith('余额'):
        return '余额 '+text
    return text

def _metric_reset(result,metric,reset_mode='absolute'):
    """单个窗口的重置时间，缩成「03:05重置」「11-07 20:01重置」或「21小时后重置」。"""
    label=str(metric.get('label','')).strip()
    if reset_mode=='countdown':
        from .reset_time import countdown_text
        return countdown_text(result,metric) or ''
    note=' '.join(str(metric.get('note','')).split())
    note=re.sub(r'^(?:5h|周)\s*重置\s*','',note)
    if not note:
        # 部分平台只给 resets_at，没有格式化好的 note。
        from datetime import datetime
        from .reset_time import reset_timestamp
        stamp=reset_timestamp(result,metric)
        if stamp:
            note=datetime.fromtimestamp(stamp).strftime('%H:%M' if label=='5h' else '%m-%d %H:%M')
    return f'{note}重置' if note else ''

def taskbar_window_rows(result,reset_mode='absolute'):
    """任务栏按窗口拆行：[{markup, reset}]。

    多窗口时每行是「额度 + 该窗口重置时间」；只有一行时额度在上、重置在下，
    由 make_rows_layout 处理。余额/积分类没有窗口，返回空列表。
    """
    if not result.ok:return []
    from .ui.floating_window import _pct_color
    from html import escape
    rows=[]
    for metric in (result.metrics or []):
        try:pct=float(metric['percent'])
        except (KeyError,TypeError,ValueError):continue
        label=str(metric.get('label','')).strip()
        color=_pct_color(pct)
        # 窗口标签（5h/周）固定深色，只有百分比跟随剩余状态着色。
        markup=(f'<span style="color:{LABEL_COLOR}; font-weight:700">{escape(label)}</span>'
                f' <span style="color:{color}; font-weight:700">{pct:.0f}%</span>')
        rows.append(dict(markup=markup,reset=_metric_reset(result,metric,reset_mode)))
    return rows

def taskbar_refresh_text(result):
    """余额类的第二行：数据刷新时刻，避免卡片只剩一行。"""
    if not result.ok:return ''
    time=str(result.updated_at).rsplit(' ',1)[-1][:5]
    return time+' 刷新' if time else ''

def rotation_candidates(rows, platforms=None):
    platforms = platforms or {}
    return [row for row in rows if row.ok and
            platforms.get(row.platform, {}).get('taskbar_enabled', True)]

def write_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(payload,ensure_ascii=False)
    if path.exists() and path.read_text(encoding='utf8')==text:return
    temp=path.with_suffix('.tmp');temp.write_text(text,encoding='utf8');temp.replace(path)

class TaskbarController(QObject):
    failed=Signal(str)
    settings_requested=Signal()
    details_requested=Signal(str)
    def __init__(self,config,window):
        super().__init__(window)
        self.config=config;self.window=window;self.rows=[];self.sequence=0
        self.root=Path(config.path).parent/'Taskbar';self.data=self.root/'Data'
        self.process=QProcess(self);self.process.finished.connect(self._finished)
        self.next_start=0;self.failures=0;self.stopping=False;self.prepared=False;self._last_content=None
        self._last_catalog=None;self._last_heartbeat=0.0
        self._rotation_platform=None;self._rotation_deadline=0;self._rotation_interval=None;self._rotation_keys=()
        self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self.tick);self.timer.start()
        self.command_timer=QTimer(self);self.command_timer.setInterval(100);self.command_timer.timeout.connect(self.read_commands);self.command_timer.start()
    def set_rows(self,rows):
        self.rows=list(rows);self.tick()
    def rotation_row(self,rows,now=None):
        now=time.monotonic() if now is None else now
        interval=rotation_seconds(self.config._data.get('taskbar_rotation_seconds',5))
        keys=tuple(row.platform for row in rows)
        if not keys:
            self._rotation_platform=None;self._rotation_keys=();return None
        if self._rotation_platform not in keys:
            self._rotation_platform=keys[0];self._rotation_deadline=now+interval
        elif interval!=self._rotation_interval or keys!=self._rotation_keys:
            self._rotation_deadline=now+interval
        elif len(keys)==1:
            self._rotation_deadline=float('inf')
        elif now>=self._rotation_deadline:
            self._rotation_platform=keys[(keys.index(self._rotation_platform)+1)%len(keys)]
            self._rotation_deadline=now+interval
        if len(keys)==1:self._rotation_deadline=float('inf')
        self._rotation_interval=interval;self._rotation_keys=keys
        return next(row for row in rows if row.platform==self._rotation_platform)
    def prepare(self):
        from .ui.floating_window import _resource_path
        source=Path(_resource_path('assets/taskbar/QuotaBoard.TaskbarHost.exe'))
        if not source.exists():raise RuntimeError('当前版本缺少内置任务栏组件，请安装完整新版。')
        self.root.mkdir(parents=True,exist_ok=True)
        target=self.root/'QuotaBoard.TaskbarHost.exe'
        if not target.exists() or hashlib.sha256(source.read_bytes()).digest()!=hashlib.sha256(target.read_bytes()).digest():
            shutil.copyfile(source,target)
        self.prepared=True
    def tick(self):
        if not self.config._data.get('taskbar_mode',False):
            self.stop();return
        try:
            self.read_commands()
            if not self.prepared:self.prepare()
            from .ui.floating_window import _dock_quota_text,_resource_path,PLATFORM_LOGO
            playable=rotation_candidates(self.rows,self.config._data.get('platforms'))
            row=self.rotation_row(playable) or QuotaResult(platform='',label='QuotaBoard',display='等待成功获取额度')
            label_full=taskbar_label(row)
            _,badge=split_period_label(label_full,row.platform)
            reset_mode=self.config._data.get('reset_display','absolute')
            window_rows=taskbar_window_rows(row,reset_mode)
            if window_rows:
                layout=make_rows_layout(window_rows,self.config._data.get('display_typography'),badge=badge)
            else:
                layout=make_layout(taskbar_quota_text(row,reset_mode),self.config._data.get('display_typography'),taskbar_refresh_text(row),badge=badge)
            details=make_details(row)
            entry=dict(id=WIDGET_ID,displayName='QuotaBoard',renderer='native',valid=True,width=layout['width'],height=layout['height'],layout=layout,permissions={},nativeRenderer=dict(expandedWidth=360,expandedHeight=detail_height(len(details)),activation='click',expandDirection='auto'),expandedLayout=expanded_layout(len(details)))
            # 目录与状态只在内容变化时落盘：任务栏组件监听这些文件，
            # 无意义的重复写入会让它在悬停/展开时反复重建浮层（表现为小窗连闪）。
            catalog=dict(schemaVersion=2,widgets=[entry])
            if catalog != self._last_catalog:
                write_json(self.data/'Runtime/WidgetCatalog.json',catalog)
                self._last_catalog=catalog
            write_json(self.data/'config.json',dict(configVersion=3,layout=dict(mode='row'),widgets=[dict(id=WIDGET_ID,widgetId=WIDGET_ID,instanceId=WIDGET_ID,enabled=bool(playable),order=0,position=self.config._data.get("taskbar_position",dict(anchorPercent=0,offsetPx=0)),settings={})],rotation=dict(intervalSeconds=rotation_seconds(self.config._data.get('taskbar_rotation_seconds',5)),widgetIds=[WIDGET_ID],instanceIds=[WIDGET_ID])))
            content=dict(platform=row.platform,label=label_full,icon=_resource_path('assets/logo/'+PLATFORM_LOGO.get(row.platform,'openai.png')))
            content['visualVersion']=hashlib.sha256(json.dumps([layout,content],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            content.update({f'line{i}':details[i] if i<len(details) else '' for i in range(11)})
            if content != self._last_content:
                self.sequence+=1
                write_json(self.data/'State'/f'{WIDGET_ID}.json',dict(schemaVersion=2,widgetId=WIDGET_ID,instanceId=WIDGET_ID,packageVersion=__version__,sequence=self.sequence,status='ok',data=content,settings={}))
                self._last_content=content
            # 心跳每 10 秒落盘一次即可判定存活；每秒重写会让组件反复重载。
            now=time.time()
            if now-self._last_heartbeat>=10:
                write_json(self.data/'managed-control.json',dict(enabled=True,owner=os.getpid(),heartbeat=now))
                self._last_heartbeat=now
            if self.process.state()==QProcess.NotRunning and time.monotonic()>=self.next_start:
                self.stopping=False
                self.process.setProgram(str(self.root/'QuotaBoard.TaskbarHost.exe'))
                self.process.setArguments(['--quotaboard-parent',str(os.getpid())]);self.process.setWorkingDirectory(str(self.root));self.process.start()
                if not self.process.waitForStarted(1500):raise RuntimeError('任务栏组件未能启动：'+self.process.errorString())
        except Exception as error:
            self.next_start=time.monotonic()+30
            if self.failures==0:self.failed.emit(str(error))
            self.failures+=1
    def read_commands(self):
        for path in sorted((self.data/'Commands').glob('*.json')):
            try:
                command=json.loads(path.read_text(encoding='utf8'))
                # A modal settings slot can enter a nested Qt event loop.
                # Consume first so that timer re-entry cannot replay it.
                path.unlink()
                if self.config._data.get('taskbar_mode',False) and command.get('widgetId')==WIDGET_ID and abs(time.time()-command.get('createdAtUnix',0))<15:
                    if command.get('action')=='openSettings':self.settings_requested.emit()
                    elif command.get('action')=='showQuotaDetails':
                        platform=command.get('platform')
                        if isinstance(platform,str) and any(r.platform==platform for r in self.rows):self.details_requested.emit(platform)
                    elif command.get('action')=='moveWidget':
                        self.config._data['taskbar_position']=dict(anchorPercent=max(0,min(100,int(command.get('positionPct',0)))),offsetPx=max(-4096,min(4096,int(command.get('offsetPx',0)))))
                        self.config.save()
            except (OSError,ValueError,TypeError):pass
            finally:
                try:path.unlink()
                except OSError:pass
    def _finished(self,code,status):
        if self.stopping:return
        self.next_start=time.monotonic()+10;self.failures+=1
        if self.failures==1:self.failed.emit('任务栏显示组件已退出，正在尝试重新连接。')
    def stop(self):
        if self.process.state()==QProcess.NotRunning:return
        self.stopping=True
        write_json(self.data/'managed-control.json',dict(enabled=False))
        self.process.waitForFinished(3500)
        if self.process.state()!=QProcess.NotRunning:self.process.kill();self.process.waitForFinished(1000)
