"""Screen-bounded taskbar details, owned by QuotaBoard rather than Explorer."""
from math import ceil
from PySide6.QtCore import Qt,QPoint,QSize,QEvent
from PySide6.QtGui import QCursor,QFont,QTextOption
from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTextBrowser,QApplication
from .floating_window import _platform_logo,_quota_details
from ..typography import typography

def detail_position(available,cursor,size):
    left=available.left()+8;top=available.top()+8
    right=max(left,available.right()-size.width()-7)
    bottom=max(top,available.bottom()-size.height()-7)
    x=max(left,min(cursor.x()-26,right))
    preferred=top if cursor.y()<=available.top()+8 else cursor.y()-size.height()-12
    return QPoint(x,max(top,min(preferred,bottom)))

class TaskbarDetailsPopup(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent,Qt.Popup|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.setWindowTitle('QuotaBoard 额度详情');self.setObjectName('taskbarDetails')
        self.setStyleSheet('''QFrame#taskbarDetails {background:#FFFFFF;border:1px solid #DDE3EB;border-radius:10px;}
QLabel {background:transparent;color:#17202B;border:none;}
QTextBrowser {background:#FFFFFF;color:#111111;border:none;font-size:12px;}
QPushButton {background:transparent;border:none;color:#738096;font-size:19px;border-radius:5px;}
QPushButton:hover {background:#EDF2F8;color:#17202B;}''')
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(18,16,18,16);self.outer.setSpacing(12)
        self.header=QHBoxLayout();self.header.setSpacing(10);self.title=QLabel();self.title.setStyleSheet('font-size:15px;font-weight:600;');self.header.addWidget(self.title,1)
        close=QPushButton('×');close.setAccessibleName('关闭详情');close.setFixedSize(28,28);close.clicked.connect(self.hide);self.header.addWidget(close);self.outer.addLayout(self.header)
        self.body=QTextBrowser();self.body.setFrameShape(QFrame.NoFrame);self.body.setOpenExternalLinks(False);self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        font=QFont('Microsoft YaHei UI');font.setPixelSize(12);self.body.document().setDefaultFont(font);self.body.document().setDocumentMargin(0)
        option=self.body.document().defaultTextOption();option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere);self.body.document().setDefaultTextOption(option)
        self.body.installEventFilter(self);self.outer.addWidget(self.body);self.logo=None;self.platform=None
    def present(self,result,cursor=None,screen=None,typography_options=None):
        cursor=cursor or QCursor.pos();screen=screen or QApplication.screenAt(cursor) or QApplication.primaryScreen();available=screen.availableGeometry()
        style=typography(typography_options)
        self.platform=result.platform;self.title.setText(result.label)
        self.title.setStyleSheet(f"font-family:'{style['family']}';font-size:{style['name_size']+3}px;font-weight:{style['weight']};")
        font=QFont(style['family']);font.setPixelSize(style['quota_size']);self.body.document().setDefaultFont(font)
        if self.logo is not None:self.header.removeWidget(self.logo);self.logo.deleteLater();self.logo=None
        self.logo=_platform_logo(result.platform,26)
        if self.logo is not None:self.header.insertWidget(0,self.logo)
        width=min(330,available.width()-24);self.setFixedWidth(width);self.body.setFixedWidth(width-36)
        self.body.setHtml(_quota_details(result,include_title=False,font_weight=style['weight'],table_width=max(64,min(260,width-64))));self.body.document().setTextWidth(width-48)
        desired=ceil(self.body.document().size().height())+12
        self.body.setFixedHeight(max(32,min(desired,available.height()-100)))
        self.outer.activate();self.adjustSize();self.move(detail_position(available,cursor,self.size()))
        self.show();self.raise_();self.activateWindow();self.setFocus(Qt.PopupFocusReason)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:self.hide();event.accept();return
        super().keyPressEvent(event)
    def eventFilter(self,watched,event):
        if event.type()==QEvent.KeyPress and event.key()==Qt.Key_Escape:self.hide();return True
        return super().eventFilter(watched,event)
