import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect,QPoint,QSize,Qt,QEvent
from PySide6.QtGui import QFontDatabase,QKeyEvent
from quotaboard.ui.taskbar_details import TaskbarDetailsPopup,detail_position
from quotaboard.model import QuotaResult
app=QApplication([])
for f in ['msyh.ttc','segoeui.ttf']:QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+f)
for rect,cursor,size in [(QRect(0,0,960,500),QPoint(15,520),QSize(330,230)),(QRect(-1280,0,1280,720),QPoint(-1270,740),QSize(330,250)),(QRect(0,40,960,500),QPoint(200,20),QSize(330,250))]:
 point=detail_position(rect,cursor,size);assert rect.contains(QRect(point,size)),(rect,point,size)
class Screen:
 def availableGeometry(self):return QRect(0,0,800,600)
popup=TaskbarDetailsPopup()
r=QuotaResult(platform='codex',label='ChatGPT',display='',metrics=[dict(label='5h',percent=86,note='5h重置 03:05'),dict(label='周',percent=29,note='周重置 11-07 20:01')])
popup.present(r,cursor=QPoint(20,630),screen=Screen());app.processEvents()
assert Screen().availableGeometry().contains(popup.geometry())
assert '刷新时间' in popup.body.toPlainText() and '20:01' in popup.body.toPlainText()
popup.grab().save('dist/taskbar-details-complete.png')
r=QuotaResult(platform='gemini',label='Gemini',display='请求失败',ok=False,error='长错误内容用于滚动校验。'*500)
popup.present(r,cursor=QPoint(790,630),screen=Screen());app.processEvents()
assert Screen().availableGeometry().contains(popup.geometry())
assert popup.body.verticalScrollBar().maximum()>0
app.sendEvent(popup.body,QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier));assert not popup.isVisible()
print('Popup bounds, multiple monitors, top/bottom placement, complete details, long-text scrolling and Escape passed')
