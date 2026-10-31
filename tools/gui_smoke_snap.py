"""GUI 冒烟：吸顶吸附（左/右/上/下边缘）。"""
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow
from quotaboard.model import QuotaResult


class _FakeScreen:
    def __init__(self, rect):
        self._rect = rect

    def availableGeometry(self):
        return self._rect


try:
    app = QApplication([])
    cfg = Config.__new__(Config)
    cfg._data = {"platforms": {"codex": {"enabled": True}},
                 "manual": {}, "cache": {}, "refresh_interval_minutes": 30}
    cfg.path = None

    w = FloatingWindow(cfg, Scheduler(cfg))
    w._results = {
        "codex": QuotaResult(
            platform="codex", label="ChatGPT",
            display="5h 76% · 周 96%", percent=76, ok=True,
            metrics=[{"label": "5h", "percent": 76, "note": ""},
                     {"label": "周", "percent": 96, "note": ""}]),
    }
    w.render()
    w.show()
    app.processEvents()

    # 模拟 1920x1080 屏幕，任务栏 40px
    scr = _FakeScreen(QRect(0, 0, 1920, 1040))
    w.screen = lambda: scr

    WW, WH = w.width(), w.height()

    def snap(x, y):
        return w._snap_rect(QRect(x, y, WW, WH))

    # 靠近顶部 → 吸到 y=0
    x1, y1 = snap(100, 12)
    assert y1 == 0, f"顶部吸附失败 y={y1}"
    # 靠近左侧 → 吸到 x=0
    x2, y2 = snap(8, 300)
    assert x2 == 0, f"左侧吸附失败 x={x2}"
    # 靠近右侧 → 吸到 x=1920-WW
    x3, y3 = snap(1920 - WW - 10, 300)
    assert x3 == 1920 - WW, f"右侧吸附失败 x={x3}"
    # 靠近底部 → 吸到 y=1040-WH
    x4, y4 = snap(100, 1040 - WH - 6)
    assert y4 == 1040 - WH, f"底部吸附失败 y={y4}"
    # 远离边缘 → 位置不变
    x5, y5 = snap(500, 500)
    assert (x5, y5) == (500, 500), f"远距离不应吸附 ({x5},{y5})"
    # 阈值外 30px → 不吸附
    x6, y6 = snap(100, 30)
    assert y6 == 30, f"30px 不应吸附 y={y6}"

    # 真实拖动流程：press→move→release 后位置被吸附
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF, QEvent, Qt
    w.move(50, 15)
    app.processEvents()
    ev_p = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(60, 25),
                       QPointF(60, 25), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    ev_m = QMouseEvent(QEvent.Type.MouseMove, QPointF(100, 8),
                       QPointF(100, 8), Qt.MouseButton.NoButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    ev_r = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(100, 8),
                       QPointF(100, 8), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    w.mousePressEvent(ev_p)
    w.mouseMoveEvent(ev_m)
    w.mouseReleaseEvent(ev_r)
    app.processEvents()
    print("after drag pos:", w.x(), w.y())
    assert w.y() == 0, f"拖动后应吸顶 y={w.y()}"

    print("GUI SNAP SMOKE OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)
