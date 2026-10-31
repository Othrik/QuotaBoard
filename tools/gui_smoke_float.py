import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow
from quotaboard.model import QuotaResult

try:
    app = QApplication([])
    cfg = Config.__new__(Config)
    cfg._data = {"platforms": {"openai": {"enabled": True}},
                 "manual": {"豆包专业版": {"total": 100, "used": 30, "unit": "次", "note": ""}},
                 "cache": {}, "refresh_interval_minutes": 30}
    cfg.path = None

    w = FloatingWindow(cfg, Scheduler(cfg))
    w._results = {
        "openai": QuotaResult(platform="openai", label="OpenAI",
                              display="$12.35", percent=62.0, ok=True),
    }
    w.render()
    w.show()
    app.processEvents()
    expanded_h = w.height()
    print("expanded h:", expanded_h)

    w.toggle()
    app.processEvents()
    collapsed_h = w.height()
    hidden = all(
        (w.body.itemAt(i).widget() is None
         or not w.body.itemAt(i).widget().isVisible())
        for i in range(w.body.count()))
    print("collapsed h:", collapsed_h, "| body hidden:", hidden)
    assert collapsed_h <= 60, "折叠态过高"
    assert hidden, "折叠态行未隐藏"

    w.toggle()
    app.processEvents()
    vis = all(
        (w.body.itemAt(i).widget() is None
         or w.body.itemAt(i).widget().isVisible())
        for i in range(w.body.count()))
    print("expanded again h:", w.height(), "| body visible:", vis)
    assert vis and w.height() > collapsed_h
    print("FLOATING SMOKE OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)
