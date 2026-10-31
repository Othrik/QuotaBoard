"""GUI 冒烟：智谱清言积分 / DeepSeek 余额行 —— 只显示数字，不画条带。"""
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QProgressBar, QLabel

from quotaboard.config import Config
from quotaboard.scheduler import Scheduler
from quotaboard.ui.floating_window import FloatingWindow
from quotaboard.model import QuotaResult


try:
    app = QApplication([])
    cfg = Config.__new__(Config)
    cfg._data = {"platforms": {"zhipu_member": {"enabled": True},
                               "deepseek": {"enabled": True}},
                 "manual": {}, "cache": {}, "refresh_interval_minutes": 30}
    cfg.path = None

    w = FloatingWindow(cfg, Scheduler(cfg))
    w._results = {
        "zhipu_member": QuotaResult(
            platform="zhipu_member", label="智谱清言",
            display="积分 23,938.48", available=23938.48, percent=None, ok=True,
            sub_note=""),
        "deepseek": QuotaResult(
            platform="deepseek", label="DeepSeek",
            display="¥100.00", percent=None, ok=True,
            sub_note=""),
    }
    w.render()
    w.show()
    app.processEvents()

    rows = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            rows.append(row)
    assert len(rows) == 2, f"应渲染 2 行，实际 {len(rows)}"

    for row in rows:
        bars = row.findChildren(QProgressBar)
        assert not bars, f"{row} 不应有进度条：{len(bars)}"
        texts = [lab.text() for lab in row.findChildren(QLabel)]
        joined = " | ".join(texts)
        print(f"row: {joined}")
    joined_all = " | ".join(
        t for row in rows for t in
        [lab.text() for lab in row.findChildren(QLabel)])
    assert "积分 23,938.48" in joined_all, joined_all
    assert "¥100.00" in joined_all, joined_all
    print("GUI TEXT SMOKE OK（智谱积分 / DeepSeek 余额均只显示数字、无条带）")
except Exception:
    traceback.print_exc()
    sys.exit(1)
