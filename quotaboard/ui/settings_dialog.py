"""Preferences: display controls, platform connections, nonblocking connection tests."""
from __future__ import annotations
from copy import deepcopy
from PySide6.QtCore import Qt,QSize,QObject,Signal,QRunnable,QThreadPool
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QDialog,QFormLayout,QFrame,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QAbstractItemView,QListWidget,QListWidgetItem,QScrollArea,QSpinBox,QStackedWidget,QVBoxLayout,QWidget)
from ..config import Config
from .. import __version__
from ..model import PLATFORM_META
from ..providers import PROVIDERS
from ..typography import typography,FAMILIES,DEFAULT_PRESET,DEFAULT_FLOATING_PRESET,floating_typography,mixed_text
from .floating_window import _resource_path,PLATFORM_LOGO

FONT_LABELS={'Microsoft YaHei UI':'微软雅黑 UI','Microsoft YaHei':'微软雅黑','DengXian':'等线',
 'SimSun':'宋体','SimHei':'黑体','KaiTi':'楷体','FangSong':'仿宋',
 'Segoe UI Variable Text':'Segoe UI Var Text','Segoe UI Variable Text Semilight':'Segoe UI Var Text Semilight','Segoe UI Variable Text Semibold':'Segoe UI Var Text Bold',
 'Segoe UI Variable Display':'Segoe UI Var Display','Segoe UI Variable Display Semilight':'Segoe UI Var Display Semilight','Segoe UI Variable Display Light':'Segoe UI Var Display Light','Segoe UI Variable Display Semibold':'Segoe UI Var Display Bold',
 'Segoe UI Variable':'Segoe UI Var（可变）','Segoe UI':'Segoe UI'}

FIELDS_LABEL={'system_token':'系统访问令牌','user_id':'用户 ID','api_key':'API Key','ak':'Access Key','sk':'Secret Key','manual_token':'手动 Token','manual_sessionid':'备用 sessionid'}
GUIDES={
 'codex':'使用已登录的 ChatGPT / Codex 账号自动读取 5 小时与每周额度，无需填写密钥。请先登录 ChatGPT Windows 应用或 Codex CLI。',
 'gemini':'先打开 Gemini 客户端并登录，程序会自动读取会员额度。首次读取被锁定的登录文件时，可能需要管理员授权。',
 'doubao':'先打开豆包客户端并登录，程序会自动读取 5 小时与每周额度。自动读取失败时，可填写备用 sessionid。',
 'zhipu_member':'使用智谱清言客户端登录态查询积分。首次读取失败时，可关闭客户端后重试，或填写备用 Token。',
 'dmxapi':'在 dmxapi.cn 个人资料中查找用户 ID，并在更多选项中取得系统访问令牌。这里填写的是系统令牌，而非模型调用 API Key。',
 'openai':'填写 OpenAI 平台 API Key，用于查询 API 账户额度。',
 'deepseek':'填写 DeepSeek 开放平台 API Key，用于查询账户余额。',
 'kimi':'填写 Moonshot / Kimi 开放平台 API Key，用于查询账户余额。',
 'zhipu':'填写智谱开放平台 API Key，用于查询 API 额度。',
 'volc':'填写火山方舟 Access Key 与 Secret Key，再选择需要查询的额度类型。',
}
STYLE='''
QDialog { background:#F5F7FB; color:#202938; font-family:'Microsoft YaHei UI','Segoe UI'; font-size:12px; }
QLabel { color:#202938; background:transparent; }
QLabel#muted { color:#768197; font-size:11px; }
QLabel#pageTitle { font-size:21px; font-weight:600; }
QFrame#card { background:#FFFFFF; border:1px solid #E4E9F1; border-radius:12px; }
QListWidget#navigation { background:#EDF1F7; border:none; border-radius:12px; padding:7px; outline:none; }
QListWidget#navigation::item { padding:11px 9px; margin:2px 0; border-radius:7px; color:#536176; }
QListWidget#navigation::item:selected { background:#FFFFFF; color:#345FD1; font-weight:600; }
QLineEdit,QSpinBox,QComboBox { background:#FFFFFF; color:#202938; border:1px solid #DCE3EE; border-radius:7px; padding:7px 9px; min-height:22px; selection-background-color:#DDE7FF; }
QLineEdit:focus,QSpinBox:focus,QComboBox:focus { border:1px solid #5E83E8; }
QPushButton { background:#FFFFFF; color:#435168; border:1px solid #DCE3EE; border-radius:7px; padding:8px 13px; }
QPushButton:hover { border-color:#A6BBEF; background:#F2F6FF; }
QPushButton:disabled { color:#A2ABBA; background:#F3F5F8; }
QPushButton#primary { background:#416BDD; color:#FFFFFF; border:none; font-weight:600; }
QPushButton#primary:hover { background:#355DCC; }
QListWidget#order { background:#FFFFFF; border:1px solid #E3E9F1; border-radius:8px; padding:4px; outline:none; }
QListWidget#order::item { padding:9px; border-bottom:1px solid #F0F3F7; }
QListWidget#order::item:selected { background:#EDF3FF; color:#315BC3; }
QScrollArea { border:none; background:transparent; }
QScrollBar:vertical { width:6px; background:transparent; margin:0; }
QScrollBar::handle:vertical { background:#CBD4E2; border-radius:3px; min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QCheckBox { spacing:9px; }
'''

class TestSignals(QObject):
    done=Signal(str,object,str)
class ConnectionTest(QRunnable):
    def __init__(self,key,cfg):
        super().__init__();self.key=key;self.cfg=cfg;self.signals=TestSignals()
    def run(self):
        try:self.signals.done.emit(self.key,PROVIDERS[self.key](self.cfg).fetch(),'')
        except Exception as error:self.signals.done.emit(self.key,None,str(error))

def muted(text):
    label=QLabel(text);label.setObjectName('muted');label.setWordWrap(True);return label

def card(title):
    box=QFrame();box.setObjectName('card');lay=QVBoxLayout(box);lay.setContentsMargins(18,16,18,16);lay.setSpacing(12)
    heading=QLabel(title);heading.setStyleSheet('font-size:14px;font-weight:600;');lay.addWidget(heading)
    return box,lay

class SettingsDialog(QDialog):
    saved=Signal()
    def __init__(self,config:Config,parent:QWidget|None=None):
        super().__init__(parent);self.config=config;self._workers={};self._type_controls={}
        self.setWindowTitle('QuotaBoard 设置');self.setMinimumSize(680,480);self.setStyleSheet(STYLE)
        # 独立普通窗口：不强制置顶，可被其他窗口遮挡、可在任务栏找到
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint,False)
        self.field_inputs={};self.enable_checks={};self.volc_actions={};self.platform_boxes={};self.test_buttons={};self.test_status={};self.nav_items={}
        self._build_ui();self._load()
        geo=QApplication.primaryScreen().availableGeometry();self.resize(min(900,geo.width()-40),min(760,geo.height()-40))
    def _scroll_page(self):
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body=QWidget();body.setObjectName('pageBody');body.setStyleSheet('QWidget#pageBody {background:transparent;}');lay=QVBoxLayout(body);lay.setContentsMargins(4,2,10,8);lay.setSpacing(16);scroll.setWidget(body)
        self.pages.addWidget(scroll);return body,lay
    def _build_ui(self):
        outer=QVBoxLayout(self);outer.setContentsMargins(18,18,18,14);outer.setSpacing(16)
        top=QHBoxLayout();title=QLabel('QuotaBoard');title.setStyleSheet('font-size:21px;font-weight:600;');top.addWidget(title);top.addStretch();top.addWidget(muted(f'偏好设置 · v{__version__}'));outer.addLayout(top)
        content=QHBoxLayout();content.setSpacing(18)
        self.navigation=QListWidget();self.navigation.setObjectName('navigation');self.navigation.setFixedWidth(186);self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.navigation.setTextElideMode(Qt.ElideRight);self.navigation.setIconSize(QSize(18,18));content.addWidget(self.navigation)
        right=QVBoxLayout();right.setSpacing(12);self.page_title=QLabel();self.page_title.setObjectName('pageTitle');right.addWidget(self.page_title)
        self.pages=QStackedWidget();right.addWidget(self.pages,1);content.addLayout(right,1);outer.addLayout(content,1)
        self.navigation.addItem('通用与显示');self._general_page()
        order_item=QListWidgetItem('AI 显示顺序');order_item.setData(Qt.UserRole,'__order__');self.navigation.addItem(order_item);self._order_page()
        font_item=QListWidgetItem('字体设置');font_item.setData(Qt.UserRole,'__fonts__');self.navigation.addItem(font_item);self._font_page()
        for key,meta in PLATFORM_META.items():
            item=QListWidgetItem(meta['label']);item.setData(Qt.UserRole,key);item.setIcon(QIcon(_resource_path('assets/logo/'+PLATFORM_LOGO.get(key,'openai.png'))));self.navigation.addItem(item);self.nav_items[key]=item;self._platform_page(key,meta)
        self.navigation.currentRowChanged.connect(self._select_page);self.navigation.setCurrentRow(0)
        footer=QHBoxLayout();hint=muted('更改将在保存后生效 · 凭据仅加密保存在本机');hint.setWordWrap(False);footer.addWidget(hint);self.save_status=QLabel('');self.save_status.setStyleSheet('color:#18966C;font-size:11px;');footer.addWidget(self.save_status);footer.addStretch()
        cancel=QPushButton('关闭');cancel.clicked.connect(self.reject);save=QPushButton('保存并刷新');save.setObjectName('primary');save.setDefault(True);save.clicked.connect(self._save);footer.addWidget(cancel);footer.addWidget(save);outer.addLayout(footer)
    def _general_page(self):
        _,lay=self._scroll_page()
        box,v=card('任务栏显示');self.taskbar_check=QCheckBox('在任务栏常驻显示 AI 额度');v.addWidget(self.taskbar_check);v.addWidget(muted('点击任务栏额度打开总览；总览卡片可分别勾选是否参与任务栏轮播。请求失败的平台暂停轮播，成功后自动恢复。'))
        row=QHBoxLayout();row.addWidget(QLabel('左右微调'));self.position_spin=QSpinBox();self.position_spin.setRange(-4096,4096);self.position_spin.setSuffix(' 像素');self.position_spin.setFixedWidth(140);row.addWidget(self.position_spin);reset=QPushButton('恢复左侧位置');reset.clicked.connect(self._reset_position);row.addWidget(reset);row.addStretch();v.addLayout(row);lay.addWidget(box)
        box,v=card('自动刷新');row=QHBoxLayout();row.addWidget(QLabel('刷新间隔'));self.interval_spin=QSpinBox();self.interval_spin.setRange(1,1440);self.interval_spin.setSuffix(' 分钟');self.interval_spin.setFixedWidth(140);row.addWidget(self.interval_spin);row.addStretch();v.addLayout(row);lay.addWidget(box)
        lay.addStretch()
    def _font_page(self):
        _,lay=self._scroll_page()
        lay.addWidget(muted('中文与西文/数字分别选择字体；每组文字共用字号和粗细。任务栏与悬浮窗分别保存，互不影响。'))
        for scope,title in [('taskbar','任务栏字体'),('floating','悬浮窗字体')]:
            box,v=card(title);form=QFormLayout();form.setSpacing(10);controls={}
            self._type_controls[scope]=controls
            roles=[('name','AI 名称'),('quota','额度 / 百分比')]
            if scope=='floating':roles.append(('note','时间 / 辅助文字'))
            for role,caption in roles:
                latin='family' if role=='name' else role+'_family'
                cjk='cjk_family' if role=='name' else role+'_cjk_family'
                weight='weight' if role=='name' else role+'_weight'
                size='name_size' if role=='name' else role+'_size'
                row=QHBoxLayout()
                for key,text in [(cjk,'中文'),(latin,'西文/数字')]:
                    combo=QComboBox();combo.setMinimumContentsLength(6);combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                    for family in FAMILIES:combo.addItem(FONT_LABELS.get(family,family),family)
                    controls[key]=combo;row.addWidget(QLabel(text));row.addWidget(combo,1)
                    combo.currentIndexChanged.connect(self._preview_typography)
                form.addRow(caption,row)
                row=QHBoxLayout();combo=QComboBox()
                for text,value in [('标准',400),('较粗',600),('粗体',700)]:combo.addItem(text,value)
                controls[weight]=combo;row.addWidget(QLabel('粗细'));row.addWidget(combo)
                spin=QSpinBox();spin.setRange(9 if role=='note' else 10,18 if role=='note' else 24 if scope=='floating' else 16 if role=='name' else 18);spin.setSuffix(' px')
                controls[size]=spin;row.addWidget(QLabel('字号'));row.addWidget(spin);row.addStretch();form.addRow('',row)
                combo.currentIndexChanged.connect(self._preview_typography);spin.valueChanged.connect(self._preview_typography)
            v.addLayout(form)
            for role,text in [('name','ChatGPT · 豆包'),('quota','5h 88% · 周 99%'),('note','刷新 20:01 · 周重置 11-07')]:
                if role=='note' and scope=='taskbar':continue
                preview=QLabel();preview.setTextFormat(Qt.RichText);preview.setProperty('sample',text)
                controls['preview_'+role]=preview;v.addWidget(preview)
            reset=QPushButton('恢复本区域默认字体');reset.clicked.connect(lambda _,s=scope:self._restore_profile(s));v.addWidget(reset)
            lay.addWidget(box)
        taskbar=self._type_controls['taskbar']
        self.font_family=taskbar['family'];self.font_weight=taskbar['weight'];self.name_size=taskbar['name_size']
        self.quota_family=taskbar['quota_family'];self.quota_weight=taskbar['quota_weight'];self.quota_size=taskbar['quota_size']
        self.name_cjk_family=taskbar['cjk_family'];self.quota_cjk_family=taskbar['quota_cjk_family']
        self.preview_name=taskbar['preview_name'];self.preview_quota=taskbar['preview_quota']
        lay.addStretch()
    def _order_page(self):
        _,lay=self._scroll_page()
        box,v=card('调整显示顺序')
        v.addWidget(muted('按住平台行拖动即可排序，也可选中后使用下方按钮。已启用的平台按此顺序展示，未启用平台在总览中置后。'))
        self.order_list=QListWidget();self.order_list.setObjectName('order')
        self.order_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.order_list.setDefaultDropAction(Qt.MoveAction)
        self.order_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.order_list.setMinimumHeight(320);self.order_list.setIconSize(QSize(22,22))
        self.order_list.setSpacing(3)
        v.addWidget(self.order_list)
        self.order_position=muted('选择平台以调整位置');v.addWidget(self.order_position)
        row=QHBoxLayout();self.order_buttons={}
        for text,action,shortcut in [('置顶',lambda:self._move_order_to(0),None),('上移',lambda:self._move_order(-1),'Alt+Up'),('下移',lambda:self._move_order(1),'Alt+Down'),('置底',lambda:self._move_order_to(self.order_list.count()-1),None)]:
            button=QPushButton(text);button.clicked.connect(action)
            if shortcut:button.setShortcut(shortcut);button.setToolTip(shortcut)
            self.order_buttons[text]=button;row.addWidget(button)
        row.addStretch();v.addLayout(row)
        self.order_reset=QPushButton('恢复默认顺序');self.order_reset.clicked.connect(lambda:self._populate_order(list(PLATFORM_META)));v.addWidget(self.order_reset)
        v.addWidget(muted('顺序同时用于总览、悬浮窗和任务栏轮播。调整后点击“保存并刷新”生效。'))
        self.order_list.currentRowChanged.connect(self._update_order_actions)
        self.order_list.model().rowsMoved.connect(self._refresh_order_labels)
        lay.addWidget(box,1)
    def _platform_page(self,key,meta):
        body,lay=self._scroll_page();self.platform_boxes[key]=body
        box,v=card('平台连接');enabled=QCheckBox('显示此平台');enabled.toggled.connect(lambda checked,k=key:self._nav_state(k,checked));self.enable_checks[key]=enabled;v.addWidget(enabled);v.addWidget(muted(GUIDES.get(key,'填写平台凭据后测试连接。')))
        inputs={};form=QFormLayout();form.setSpacing(12)
        for field,_ in meta['credential_fields']:
            row=QHBoxLayout();ed=QLineEdit();ed.setEchoMode(QLineEdit.Password);ed.setPlaceholderText('未配置');row.addWidget(ed,1)
            reveal=QPushButton('显示');reveal.setCheckable(True);reveal.setFixedWidth(64)
            reveal.toggled.connect(lambda checked,e=ed,b=reveal:(e.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password),b.setText('隐藏' if checked else '显示')));row.addWidget(reveal);form.addRow(FIELDS_LABEL.get(field,field),row);inputs[field]=ed
        self.field_inputs[key]=inputs
        if inputs:v.addLayout(form);v.addWidget(muted('已保存的凭据无需重复填写；输入新值后保存即可替换。'))
        if key=='volc':
            combo=QComboBox();combo.addItems(['套餐用量（GetUsageDetails）','模型推理限额（ListModelInferenceLimits）']);self.volc_actions[key]=combo;v.addWidget(combo)
        row=QHBoxLayout();button=QPushButton('测试连接');button.clicked.connect(lambda _,k=key:self._test(k));row.addWidget(button);row.addStretch();v.addLayout(row)
        status=QLabel('测试仅检查连接，不会保存本页更改。');status.setWordWrap(True);status.setObjectName('muted');v.addWidget(status);self.test_buttons[key]=button;self.test_status[key]=status;lay.addWidget(box);lay.addStretch()
    def _select_page(self,index):
        if index<0:return
        self.pages.setCurrentIndex(index);item=self.navigation.item(index);self.page_title.setText('通用与显示' if index==0 else 'AI 显示顺序' if item.data(Qt.UserRole)=='__order__' else '字体设置' if item.data(Qt.UserRole)=='__fonts__' else PLATFORM_META[item.data(Qt.UserRole)]['label'])
    def _nav_state(self,key,checked):
        self.nav_items[key].setText(PLATFORM_META[key]['label']+(' · 已启用' if checked else ''))
        self._refresh_order_labels()
    def _reset_position(self):self._anchor_percent=0;self.position_spin.setValue(0)
    def _populate_order(self,keys):
        self.order_list.clear()
        for key in keys:
            item=QListWidgetItem();item.setData(Qt.UserRole,key)
            item.setIcon(QIcon(_resource_path('assets/logo/'+PLATFORM_LOGO.get(key,'openai.png'))))
            item.setSizeHint(QSize(0,38));self.order_list.addItem(item)
        self.order_list.setCurrentRow(0);self._refresh_order_labels()
    def _refresh_order_labels(self,*_):
        for i in range(self.order_list.count()):
            item=self.order_list.item(i);key=item.data(Qt.UserRole)
            state='已启用' if self.enable_checks[key].isChecked() else '未启用'
            item.setText(f"{i+1:02d}   {PLATFORM_META[key]['label']}   ·   {state}")
        self._update_order_actions()
    def _update_order_actions(self,*_):
        row=self.order_list.currentRow();count=self.order_list.count()
        for name in ('置顶','上移'):self.order_buttons[name].setEnabled(row>0)
        for name in ('下移','置底'):self.order_buttons[name].setEnabled(0<=row<count-1)
        self.order_position.setText(f'第 {row+1} / {count} 位 · 保存后生效' if row>=0 else '选择平台以调整位置')
        keys=[self.order_list.item(i).data(Qt.UserRole) for i in range(count)]
        self.order_reset.setEnabled(keys!=list(PLATFORM_META))
    def _move_order_to(self,new):
        old=self.order_list.currentRow()
        if old>=0 and 0<=new<self.order_list.count() and old!=new:
            item=self.order_list.takeItem(old);self.order_list.insertItem(new,item)
            self.order_list.setCurrentRow(new);self.order_list.scrollToItem(item)
            self._refresh_order_labels()
    def _move_order(self,delta):
        self._move_order_to(self.order_list.currentRow()+delta)
    def _profile_value(self,scope):
        controls=self._type_controls[scope];values={}
        for key in DEFAULT_PRESET:
            if key not in controls:continue
            control=controls[key];values[key]=control.value() if isinstance(control,QSpinBox) else control.currentData()
        return typography(values,floating=scope=='floating')
    def _typography_value(self):return self._profile_value('taskbar')
    def _set_profile(self,scope,style):
        for key,control in self._type_controls[scope].items():
            if key.startswith('preview_'):continue
            if isinstance(control,QSpinBox):control.setValue(style[key])
            else:control.setCurrentIndex(max(0,control.findData(style[key])))
    def _restore_profile(self,scope):
        self._set_profile(scope,DEFAULT_FLOATING_PRESET if scope=='floating' else DEFAULT_PRESET)
        self._preview_typography()
    def _restore_typography_defaults(self):self._restore_profile('taskbar')
    def _preview_typography(self):
        for scope,controls in self._type_controls.items():
            style=self._profile_value(scope)
            for role in ('name','quota','note'):
                preview=controls.get('preview_'+role)
                if preview is not None:preview.setText(mixed_text(preview.property('sample'),style,role))
    def _load(self):
        for key,meta in PLATFORM_META.items():
            self.enable_checks[key].setChecked(self.config.is_enabled(key))
            for field,_ in meta['credential_fields']:
                saved=bool(self.config.get_credential(key,field));self.field_inputs[key][field].setPlaceholderText('已保存，留空保留' if saved else '未配置')
            if key=='volc':self.volc_actions[key].setCurrentIndex(1 if self.config.platform_cfg(key).get('action')=='ListModelInferenceLimits' else 0)
        self._set_profile('taskbar',typography(self.config._data.get('display_typography')))
        self._set_profile('floating',floating_typography(self.config._data))
        self._preview_typography()
        self.interval_spin.setValue(self.config.refresh_interval_minutes);self.taskbar_check.setChecked(bool(self.config._data.get('taskbar_mode',False)))
        position=self.config._data.get('taskbar_position',{});self._anchor_percent=position.get('anchorPercent',0);self.position_spin.setValue(position.get('offsetPx',0))
        self._populate_order(self.config.platform_order)
    def _test(self,key):
        if key in self._workers:return
        cfg={f:ed.text().strip() or self.config.get_credential(key,f) for f,ed in self.field_inputs[key].items()}
        if key=='volc':cfg['action']='ListModelInferenceLimits' if self.volc_actions[key].currentIndex()==1 else 'GetUsageDetails'
        self.test_buttons[key].setEnabled(False);self.test_buttons[key].setText('正在测试…');self.test_status[key].setStyleSheet('color:#768197;');self.test_status[key].setText('正在连接，请稍候；你可以继续调整其他设置。')
        worker=ConnectionTest(key,cfg);worker.signals.done.connect(self._test_done);self._workers[key]=worker;QThreadPool.globalInstance().start(worker)
    def _test_done(self,key,result,error):
        self._workers.pop(key,None);self.test_buttons[key].setEnabled(True);self.test_buttons[key].setText('重新测试')
        ok=result is not None and result.ok;self.test_status[key].setStyleSheet('color:'+('#18966C' if ok else '#D44D60')+';')
        self.test_status[key].setText('连接成功 · '+result.display if ok else '连接失败 · '+(error or (result.error if result else '') or '暂时无法获取额度'))
    def _save(self):
        previous=deepcopy(self.config._data)
        try:
            for key,meta in PLATFORM_META.items():
                self.config.set_enabled(key,self.enable_checks[key].isChecked())
                for field,_ in meta['credential_fields']:
                    text=self.field_inputs[key][field].text().strip()
                    if text:self.config.set_credential(key,field,text)
                if key=='volc':self.config.platform_cfg(key)['action']='ListModelInferenceLimits' if self.volc_actions[key].currentIndex()==1 else 'GetUsageDetails'
            self.config._data['display_typography']=self._typography_value()
            self.config._data['floating_typography']=self._profile_value('floating')
            self.config._data['taskbar_mode']=self.taskbar_check.isChecked();self.config._data['taskbar_position']=dict(anchorPercent=self._anchor_percent,offsetPx=self.position_spin.value());self.config.refresh_interval_minutes=self.interval_spin.value()
            self.config.platform_order=[self.order_list.item(i).data(Qt.UserRole) for i in range(self.order_list.count())];self.config.save()
        except Exception as error:
            self.config._data=previous;QMessageBox.critical(self,'保存失败',str(error));return
        # 保存后保持设置面板显示（不自动关闭、不最小化），立即刷新额度并给出反馈
        self.save_status.setText('已保存并刷新额度')
        self.saved.emit()
        self.raise_()
        self.activateWindow()
