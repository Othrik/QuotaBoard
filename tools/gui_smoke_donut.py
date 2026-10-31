import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow, _Donut
from quotaboard.model import QuotaResult

def count_donuts(lay, acc: list) -> None:
    for i in range(lay.count()):
        item = lay.itemAt(i)
        w = item.widget()
        if isinstance(w, _Donut):
            acc.append(w)
        sub = item.layout()
        if sub is not None:
            count_donuts(sub, acc)


try:
    app = QApplication([])
    cfg = Config.__new__(Config)
    cfg._data = {"platforms": {"codex": {"enabled": True}},
                 "manual": {}, "cache": {}, "refresh_interval_minutes": 30}
    cfg.path = None

    w = FloatingWindow(cfg, Scheduler(cfg))
    w._results = {
        "codex": QuotaResult(
            platform="codex", label="ChatGPT 用量（5h/周）",
            display="5h 76% · 周 96%", percent=76, ok=True,
            sub_note="5h重置 01:01 · 周重置 20:01",
            metrics=[{"label": "5h", "percent": 76, "note": "5h重置 01:01"},
                     {"label": "周", "percent": 96, "note": "周重置 20:01"}]),
    }
    w.render()
    w.show()
    app.processEvents()

    donuts: list = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            count_donuts(row.layout(), donuts)
    print("donut count:", len(donuts))
    assert len(donuts) == 2, "应渲染 2 个环形图"
    print("labels:", [d._label for d in donuts])
    print("expanded h:", w.height())
    w.toggle()
    app.processEvents()
    print("collapsed h:", w.height())
    assert w.height() <= 60
    print("GUI DONUT SMOKE OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)
