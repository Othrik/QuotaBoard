"""单实例：第二个 QuotaBoard 必须被内核互斥量拦下，不能同时写任务栏状态。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication

import main

app = QApplication([])
assert main._acquire_windows_mutex() is True, '第一个实例应拿到互斥量'
assert main._acquire_windows_mutex() is False, '第二个实例必须被拦下'
assert main._acquire_windows_mutex() is False, '重复启动同样要拦下'
print('Single instance mutex guard passed')
