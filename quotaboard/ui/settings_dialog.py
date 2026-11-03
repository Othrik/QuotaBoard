"""Preferences: display controls, platform connections, nonblocking connection tests."""
from __future__ import annotations
from copy import deepcopy
from PySide6.QtCore import Qt,QSize,QObject,Signal,QRunnable,QThreadPool
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QDialog,QFormLayout,QFrame,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QAbstractItemView,QListWidget,QListWidgetItem,QScrollArea,QSpinBox,QStackedWidget,QVBoxLayout,QWidget)
from ..config import Config
from ..model import PLATFORM_META
from ..providers import PROVIDERS
from ..typography import typography,FAMILIES,DEFAULT_PRESET
from .floating_window import _resource_path,PLATFORM_LOGO

FONT_LABELS={'Microsoft YaHei UI':'微软雅黑 UI','Microsoft YaHei':'微软雅黑','DengXian':'等线',
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
        super().__init__(parent);self.config=config;self._workers={}
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
        top=QHBoxLayout();title=QLabel('QuotaBoard');title.setStyleSheet('font-size:21px;font-weight:600;');top.addWidget(title);top.addStretch();top.addWidget(muted('偏好设置'));outer.addLayout(top)
        content=QHBoxLayout();content.setSpacing(18)
        self.navigation=QListWidget();self.navigation.setObjectName('navigation');self.navigation.setFixedWidth(186);self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.navigation.setTextElideMode(Qt.ElideRight);self.navigation.setIconSize(QSize(18,18));content.addWidget(self.navigation)
        right=QVBoxLayout();right.setSpacing(12);self.page_title=QLabel();self.page_title.setObjectName('pageTitle');right.addWidget(self.page_title)
        self.pages=QStackedWidget();right.addWidget(self.pages,1);content.addLayout(right,1);outer.addLayout(content,1)
        self.navigation.addItem('通用与显示');self._general_page()
        for key,meta in PLATFORM_META.items():
            item=QListWidgetItem(meta['label']);item.setData(Qt.UserRole,key);item.setIcon(QIcon(_resource_path('assets/logo/'+PLATFORM_LOGO.get(key,'openai.png'))));self.navigation.addItem(item);self.nav_items[key]=item;self._platform_page(key,meta)
        self.navigation.currentRowChanged.connect(self._select_page);self.navigation.setCurrentRow(0)
        footer=QHBoxLayout();hint=muted('更改将在保存后生效 · 凭据仅加密保存在本机');hint.setWordWrap(False);footer.addWidget(hint);self.save_status=QLabel('');self.save_status.setStyleSheet('color:#18966C;font-size:11px;');footer.addWidget(self.save_status);footer.addStretch()
        cancel=QPushButton('关闭');cancel.clicked.connect(self.reject);save=QPushButton('保存并刷新');save.setObjectName('primary');save.setDefault(True);save.clicked.connect(self._save);footer.addWidget(cancel);footer.addWidget(save);outer.addLayout(footer)
    def _general_page(self):
        _,lay=self._scroll_page()
        box,v=card('任务栏显示');self.taskbar_check=QCheckBox('在任务栏常驻显示 AI 额度');v.addWidget(self.taskbar_check);v.addWidget(muted('点击查看详情，右键打开设置。请求失败的平台暂停轮播，成功后自动恢复。'))
        row=QHBoxLayout();row.addWidget(QLabel('左右微调'));self.position_spin=QSpinBox();self.position_spin.setRange(-4096,4096);self.position_spin.setSuffix(' 像素');self.position_spin.setFixedWidth(140);row.addWidget(self.position_spin);reset=QPushButton('恢复左侧位置');reset.clicked.connect(self._reset_position);row.addWidget(reset);row.addStretch();v.addLayout(row);lay.addWidget(box)
        box,v=card('名称与额度字体');form=QFormLayout();form.setSpacing(10)
        def font_combo():
            combo=QComboBox()
            for family in FAMILIES:combo.addItem(FONT_LABELS.get(family,family),family)
            return combo
        def weight_combo():
            combo=QComboBox()
            for label,weight in [('标准',400),('较粗',600),('粗体',700)]:combo.addItem(label,weight)
            return combo
        self.font_family=font_combo();self.font_weight=weight_combo();self.quota_family=font_combo();self.quota_weight=weight_combo()
        self.name_size=QSpinBox();self.name_size.setRange(10,16);self.name_size.setSuffix(' px');self.quota_size=QSpinBox();self.quota_size.setRange(10,18);self.quota_size.setSuffix(' px')
        row=QHBoxLayout();row.addWidget(QLabel('字体'));row.addWidget(self.font_family,1);row.addSpacing(8);row.addWidget(QLabel('粗细'));row.addWidget(self.font_weight);row.addSpacing(8);row.addWidget(QLabel('字号'));row.addWidget(self.name_size);form.addRow('AI 名称',row)
        row=QHBoxLayout();row.addWidget(QLabel('字体'));row.addWidget(self.quota_family,1);row.addSpacing(8);row.addWidget(QLabel('粗细'));row.addWidget(self.quota_weight);row.addSpacing(8);row.addWidget(QLabel('字号'));row.addWidget(self.quota_size);form.addRow('额度数字',row)
        v.addLayout(form)
        preset=QPushButton('恢复默认（名称 Text / 额度 Display，均为较粗 12px）');preset.clicked.connect(self._restore_typography_defaults);v.addWidget(preset)
        preview=QHBoxLayout();self.preview_name=QLabel('ChatGPT');self.preview_quota=QLabel('5h 88% · 周 99%');preview.addWidget(self.preview_name);preview.addWidget(self.preview_quota);preview.addStretch();v.addLayout(preview)
        v.addWidget(muted('名称与额度可分别设置字体、粗细与字号；任务栏与展示板共用这套组合。'))
        for control in [self.font_family,self.font_weight,self.quota_family,self.quota_weight]:control.currentIndexChanged.connect(self._preview_typography)
        for control in [self.name_size,self.quota_size]:control.valueChanged.connect(self._preview_typography)
        lay.addWidget(box)
        box,v=card('自动刷新');row=QHBoxLayout();row.addWidget(QLabel('刷新间隔'));self.interval_spin=QSpinBox();self.interval_spin.setRange(1,1440);self.interval_spin.setSuffix(' 分钟');self.interval_spin.setFixedWidth(140);row.addWidget(self.interval_spin);row.addStretch();v.addLayout(row);lay.addWidget(box)
        box,v=card('AI 显示顺序');v.addWidget(muted('拖动调整顺序，或选中平台后使用上移、下移。展示板和任务栏共用此顺序。'))
        self.order_list=QListWidget();self.order_list.setObjectName('order');self.order_list.setDragDropMode(QAbstractItemView.InternalMove);self.order_list.setDefaultDropAction(Qt.MoveAction);self.order_list.setFixedHeight(156);self.order_list.setIconSize(QSize(18,18));v.addWidget(self.order_list)
        row=QHBoxLayout()
        for text,delta in [('上移',-1),('下移',1)]:
            button=QPushButton(text);button.clicked.connect(lambda _,d=delta:self._move_order(d));row.addWidget(button)
        row.addStretch();v.addLayout(row);lay.addWidget(box);lay.addStretch()
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
        self.pages.setCurrentIndex(index);item=self.navigation.item(index);self.page_title.setText('通用与显示' if index==0 else PLATFORM_META[item.data(Qt.UserRole)]['label'])
    def _nav_state(self,key,checked):
        self.nav_items[key].setText(PLATFORM_META[key]['label']+(' · 已启用' if checked else ''))
    def _reset_position(self):self._anchor_percent=0;self.position_spin.setValue(0)
    def _move_order(self,delta):
        old=self.order_list.currentRow();new=old+delta
        if old>=0 and 0<=new<self.order_list.count():self.order_list.insertItem(new,self.order_list.takeItem(old));self.order_list.setCurrentRow(new)
    def _typography_value(self):
        return typography(dict(family=self.font_family.currentData(),weight=self.font_weight.currentData(),name_size=self.name_size.value(),
                               quota_family=self.quota_family.currentData(),quota_weight=self.quota_weight.currentData(),quota_size=self.quota_size.value()))
    def _restore_typography_defaults(self):
        self.font_family.setCurrentIndex(max(0,self.font_family.findData(DEFAULT_PRESET['family'])))
        self.font_weight.setCurrentIndex(max(0,self.font_weight.findData(DEFAULT_PRESET['weight'])))
        self.name_size.setValue(DEFAULT_PRESET['name_size'])
        self.quota_family.setCurrentIndex(max(0,self.quota_family.findData(DEFAULT_PRESET['quota_family'])))
        self.quota_weight.setCurrentIndex(max(0,self.quota_weight.findData(DEFAULT_PRESET['quota_weight'])))
        self.quota_size.setValue(DEFAULT_PRESET['quota_size'])
        self._preview_typography()
    def _preview_typography(self):
        style=self._typography_value()
        self.preview_name.setStyleSheet(f"font-family:'{style['family']}';font-size:{style['name_size']}px;font-weight:{style['weight']};")
        self.preview_quota.setStyleSheet(f"font-family:'{style['quota_family']}';font-size:{style['quota_size']}px;font-weight:{style['quota_weight']};color:#219C77;")
    def _load(self):
        for key,meta in PLATFORM_META.items():
            self.enable_checks[key].setChecked(self.config.is_enabled(key))
            for field,_ in meta['credential_fields']:
                saved=bool(self.config.get_credential(key,field));self.field_inputs[key][field].setPlaceholderText('已保存，留空保留' if saved else '未配置')
            if key=='volc':self.volc_actions[key].setCurrentIndex(1 if self.config.platform_cfg(key).get('action')=='ListModelInferenceLimits' else 0)
        style=typography(self.config._data.get('display_typography'))
        self.font_family.setCurrentIndex(max(0,self.font_family.findData(style['family'])))
        self.font_weight.setCurrentIndex(max(0,self.font_weight.findData(style['weight'])))
        self.name_size.setValue(style['name_size'])
        self.quota_family.setCurrentIndex(max(0,self.quota_family.findData(style['quota_family'])))
        self.quota_weight.setCurrentIndex(max(0,self.quota_weight.findData(style['quota_weight'])))
        self.quota_size.setValue(style['quota_size'])
        self._preview_typography()
        self.interval_spin.setValue(self.config.refresh_interval_minutes);self.taskbar_check.setChecked(bool(self.config._data.get('taskbar_mode',False)))
        position=self.config._data.get('taskbar_position',{});self._anchor_percent=position.get('anchorPercent',0);self.position_spin.setValue(position.get('offsetPx',0))
        for key in self.config.platform_order:
            item=QListWidgetItem(PLATFORM_META[key]['label']);item.setData(Qt.UserRole,key);item.setIcon(QIcon(_resource_path('assets/logo/'+PLATFORM_LOGO.get(key,'openai.png'))));self.order_list.addItem(item)
        self.order_list.setCurrentRow(0)
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
            self.config._data['taskbar_mode']=self.taskbar_check.isChecked();self.config._data['taskbar_position']=dict(anchorPercent=self._anchor_percent,offsetPx=self.position_spin.value());self.config.refresh_interval_minutes=self.interval_spin.value()
            self.config.platform_order=[self.order_list.item(i).data(Qt.UserRole) for i in range(self.order_list.count())];self.config.save()
        except Exception as error:
            self.config._data=previous;QMessageBox.critical(self,'保存失败',str(error));return
        # 保存后保持设置面板显示（不自动关闭、不最小化），立即刷新额度并给出反馈
        self.save_status.setText('已保存并刷新额度')
        self.saved.emit()
        self.raise_()
        self.activateWindow()
