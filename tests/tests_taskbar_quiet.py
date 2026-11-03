"""任务栏托管：避免无意义重写导致的浮层连闪。

1) 同一份内容重复 tick 不再重写 WidgetCatalog / State；
2) 心跳降频到 10 秒，不再每秒落盘；
3) 展开触发方式为点击（悬停不再自动弹小窗）。
"""
import json
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from quotaboard.config import Config
from quotaboard.model import QuotaResult
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow
import quotaboard.taskbar as tb

app = QApplication([])


def make_controller(root: Path):
    cfg = Config.__new__(Config)
    cfg._data = {'platforms': {}, 'cache': {}, 'taskbar_mode': True,
                 'display_typography': None, 'taskbar_position': {}}
    cfg.save = lambda: None
    cfg.path = str(root / 'config.json')
    window = FloatingWindow(cfg, Scheduler(cfg))
    ctl = tb.TaskbarController(cfg, window)
    ctl.prepared = True
    ctl.prepare = lambda: None
    ctl.next_start = float('inf')  # 不真正启动 helper
    return ctl


root = Path(tempfile.mkdtemp())
ctl = make_controller(root)
row = QuotaResult(platform='codex', label='ChatGPT', display='5h 80% · 周 40%')

calls = []
real_write = tb.write_json


def spy(path, payload):
    calls.append((Path(path).name, json.dumps(payload, ensure_ascii=False, sort_keys=True)))


tb.write_json = spy
try:
    ctl.set_rows([row])      # 内部 tick 一次
    ctl.tick()
    ctl.tick()
finally:
    tb.write_json = real_write

names = [name for name, _ in calls]
assert names.count('WidgetCatalog.json') == 1, f'目录应只写一次，实际 {names}'
assert names.count('com.othrik.quotaboard.json') == 1, f'状态应只写一次，实际 {names}'
assert names.count('managed-control.json') == 1, f'心跳应每秒最多一次、这里三次 tick 只写一次，实际 {names}'
catalog = next(payload for name, payload in calls if name == 'WidgetCatalog.json')
assert json.loads(catalog)['widgets'][0]['nativeRenderer']['activation'] == 'click', '展开方式应为点击'

# 真实落盘：心跳 10 秒内不刷新时间戳
ctl2 = make_controller(root)
real = root / 'Taskbar' / 'Data' / 'managed-control.json'
ctl2.tick()
first = real.stat().st_mtime_ns
time.sleep(1.2)
ctl2.tick()
assert real.stat().st_mtime_ns == first, '心跳不应在 10 秒内重复写入'

print('Taskbar quiet writes, throttled heartbeat and click activation passed')
