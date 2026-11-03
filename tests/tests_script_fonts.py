"""Chinese/western fonts are explicit, and floating settings are independent."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtGui import QFontDatabase,QFont,QTextDocument
from quotaboard.config import Config
from quotaboard.model import QuotaResult
from quotaboard.scheduler import Scheduler
from quotaboard.typography import typography,floating_typography,script_runs,mixed_text
from quotaboard.taskbar_layout import make_layout
from quotaboard.ui.settings_dialog import SettingsDialog
from quotaboard.ui.floating_window import FloatingWindow,_Donut

app=QApplication([])
for font in ('msyh.ttc','msyhbd.ttc','segoeui.ttf','consola.ttf','simsun.ttc'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
app.setFont(QFont('Microsoft YaHei UI',9))
style=typography(dict(family='Consolas',cjk_family='SimHei',quota_family='Arial',quota_cjk_family='SimSun'))
text='智谱 GLM · 5h 88% 周'
assert ''.join(run for run,_ in script_runs(text))==text
doc=QTextDocument();doc.setHtml(mixed_text(text,style))
assert doc.toPlainText()==text
fragments=[];iterator=doc.begin().begin()
while not iterator.atEnd():
    fragment=iterator.fragment()
    fragments.append((fragment.text(),fragment.charFormat().fontFamilies()))
    iterator+=1
assert any('智谱' in text and 'SimHei' in families for text,families in fragments)
assert any('GLM' in text and 'Consolas' in families for text,families in fragments)
layout=make_layout('5h 88% · 周 99%',style,'智谱 GLM · Plus')
title=layout['children'][0]['children'][1]['children'][0]['children']
values=layout['children'][0]['children'][1]['children'][1]['children']
assert any(p.get('text')=='智谱' and p['fontFamily']=='SimHei' for p in title)
assert any(p.get('text')=='GLM' and p['fontFamily']=='Consolas' for p in title)
assert any(p.get('text')=='周' and p['fontFamily']=='SimSun' for p in values)
assert any(p.get('text')=='99%' and p['fontFamily']=='Arial' for p in values)

config=Config(Path('dist/script-font-test/config.json'))
config._data['display_typography']=style
config._data.pop('floating_typography',None)
config.set_enabled('codex',True)
config.save=lambda:None
assert floating_typography(config._data)['name_size']==style['name_size']+2
dialog=SettingsDialog(config)
dialog.font_family.setCurrentIndex(dialog.font_family.findData('Consolas'))
dialog.name_cjk_family.setCurrentIndex(dialog.name_cjk_family.findData('SimHei'))
controls=dialog._type_controls['floating']
for key,value in dict(family='Arial',cjk_family='SimSun',quota_family='Consolas',quota_cjk_family='Microsoft YaHei UI',note_family='Calibri',note_cjk_family='SimSun').items():
    controls[key].setCurrentIndex(controls[key].findData(value))
controls['name_size'].setValue(24);controls['quota_size'].setValue(24);controls['note_size'].setValue(18)
dialog._save()
saved=floating_typography(config._data)
assert saved['family']=='Arial' and config._data['display_typography']['family']=='Consolas'
assert saved['cjk_family']=='SimSun' and config._data['display_typography']['cjk_family']=='SimHei'
assert (saved['name_size'],saved['quota_size'],saved['note_size'])==(24,24,18)
window=FloatingWindow(config,Scheduler(config))
window.on_results({'codex':QuotaResult('codex','ChatGPT 智能','80%',metrics=[dict(label='5h',percent=80),dict(label='周',percent=50)],sub_note='5h重置 20:01 · 周重置 11-07 20:01')})
app.processEvents()
donuts=window.findChildren(_Donut)
assert len(donuts)==2 and all(d._font_size==24 and d._font_family=='Consolas' for d in donuts)
assert all(d.width()>46 and d.height()>55 for d in donuts)
assert window.width()<=window.screen().availableGeometry().width()
assert 'SimSun' in window.findChild(QLabel,'platformName').text()
window.show();app.processEvents();window.grab().save('dist/floating-font-preview.png')
window.hide()
dialog.navigation.setCurrentRow(2)
assert dialog.page_title.text()=='字体设置'
dialog.resize(1000,800);dialog.show();app.processEvents();dialog.grab().save('dist/font-settings-preview.png')
dialog.hide()
print('Explicit CJK/western glyph fonts, native runs, independent saved profiles and large floating donuts passed')
