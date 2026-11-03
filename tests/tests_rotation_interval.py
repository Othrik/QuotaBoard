from PySide6.QtCore import QCoreApplication,QObject
from quotaboard.taskbar import TaskbarController,rotation_candidates
from quotaboard.model import QuotaResult
from quotaboard.rotation import rotation_seconds

app=QCoreApplication.instance() or QCoreApplication([])
class Config:
    path='dist/rotation-interval-test/config.json'
    _data={'taskbar_rotation_seconds':5}
owner=QObject();config=Config();controller=TaskbarController(config,owner)
controller.timer.stop();controller.command_timer.stop()
rows=[QuotaResult('codex','ChatGPT','80%'),QuotaResult('gemini','Gemini','90%')]
assert controller.rotation_row(rows,100).platform=='codex'
assert controller.rotation_row(rows,104.9).platform=='codex'
assert controller.rotation_row(rows,105).platform=='gemini'
# Refreshing values must not restart the dwell timer.
assert controller.rotation_row(rows,107).platform=='gemini'
assert controller.rotation_row(rows,110).platform=='codex'
config._data['taskbar_rotation_seconds']=12
assert controller.rotation_row(rows,111).platform=='codex'
assert controller.rotation_row(rows,122.9).platform=='codex'
assert controller.rotation_row(rows,123).platform=='gemini'
# A removed/failed platform is not kept on screen until its timer expires.
rows[1].ok=False
assert controller.rotation_row(rotation_candidates(rows),124).platform=='codex'
assert controller.rotation_row([],125) is None
rows[1].ok=True
assert controller.rotation_row(rows,126).platform=='codex'
assert controller.rotation_row(rows,138).platform=='gemini'
assert rotation_seconds(None)==5 and rotation_seconds('invalid')==5
assert rotation_seconds(0)==1 and rotation_seconds(999)==300
print('Full dwell time, runtime speed change, refresh stability, failure removal and interval bounds passed')
