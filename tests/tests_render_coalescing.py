"""回归：同一轮刷新的多次结果只能重建一次，且指针悬停时不重建。"""
import os,types
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent
from quotaboard.config import Config
from quotaboard.model import QuotaResult
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow
app=QApplication([])
c=Config.__new__(Config)
keys=('codex','gemini','doubao')
c._data={'platforms':{k:{'enabled':True} for k in keys},'cache':{},'platform_order':list(keys),'taskbar_mode':False}
c.save=lambda:None
w=FloatingWindow(c,Scheduler(c));w.show();app.processEvents()
calls=[];real=w._render_now
def counted(self):
    calls.append(1);real()
w._render_now=types.MethodType(counted,w)
w._hover_on_board=lambda: False
# 一轮刷新里每个平台各回调一次
for i,k in enumerate(keys):
    w.on_partial_result(k,QuotaResult(platform=k,label=k,display=f'{i}%'))
app.processEvents();app.processEvents()
assert len(calls)==1,'一轮刷新只能重绘一次，实际 %d 次'%len(calls)
assert w.body.count()==len(keys)
# 指针停在面板上：推迟重建，不产生新的行/widget 抖动
calls.clear()
w._hover_on_board=lambda: True
w.request_render();app.processEvents();app.processEvents()
assert not calls,'指针悬停在面板上时不应重建'
assert w._render_pending,'推迟的重绘必须被记住'
# 指针离开后补做
w._hover_on_board=lambda: False
w.leaveEvent(QEvent(QEvent.Type.Leave));app.processEvents();app.processEvents()
assert len(calls)==1,'指针离开后应补做一次重建'
assert not w._render_pending
# 悬停卡片文本不变时不重复 show
w._hover_popup.present('A\u000aB',w.mapToGlobal(w.rect().center()))
app.processEvents()
assert w._hover_popup.isVisible()
w._hover_popup.present('A\u000aB',w.mapToGlobal(w.rect().center()))
assert w._hover_popup.isVisible()
w._hover_popup.hide()
print('Render coalescing, hover deferral and popup reuse passed')
