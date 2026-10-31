"""GUI 冒烟：豆包行渲染 + 折叠态（自适应高度/按钮图标）+ 双圈。"""
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


def row_labels(w) -> list[str]:
    out = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            names = [lab.text() for lab in row.findChildren(type(row.children()[0]))
                     if isinstance(lab, type(w.head_title))]
            # 简化：直接取行的子 QLabel 第一个
            out.append(names)
    return out


try:
    app = QApplication([])
    cfg = Config.__new__(Config)
    cfg._data = {"platforms": {"doubao": {"enabled": True},
                               "codex": {"enabled": True}},
                 "manual": {}, "cache": {},
                 "refresh_interval_minutes": 30}
    cfg.path = None

    w = FloatingWindow(cfg, Scheduler(cfg))
    w._results = {
        "codex": QuotaResult(
            platform="codex", label="ChatGPT",
            display="5h 76% · 周 96%", percent=76, ok=True,
            sub_note="5h重置 01:01 · 周重置 20:01",
            metrics=[{"label": "5h", "percent": 76, "note": "5h重置 01:01"},
                     {"label": "周", "percent": 96, "note": "周重置 20:01"}]),
        "doubao": QuotaResult(
            platform="doubao", label="豆包",
            display="5h 47% · 周 16%", percent=16, ok=True,
            sub_note="个人订阅 · 2026-11-12到期 · 活动赠送 6%",
            metrics=[{"label": "5h", "percent": 47, "note": "5h 792 / 1,470"},
                     {"label": "周", "percent": 16, "note": "周 3,537 / 4,200"}]),
    }
    w.render()
    w.show()
    app.processEvents()

    # 展开态：应有两行（ChatGPT、豆包）
    rows_visible = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            rows_visible.append(row.isVisible())
            # 每行名称标签文本
            for lab in row.findChildren(type(w.head_title)):
                pass
    print("rows count:", w.body.count(), "visible:", rows_visible)
    assert w.body.count() == 2, f"应渲染 2 行，实际 {w.body.count()}"

    # 展开态豆包行可见 + 双圈
    donuts: list = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            count_donuts(row.layout(), donuts)
    print("donut count:", len(donuts))
    assert len(donuts) == 4, f"两行共 4 个环形图，实际 {len(donuts)}"
    print("donut labels:", [d._label for d in donuts])
    print("expanded w/h:", w.width(), w.height())
    assert w.width() == 330

    # 折叠态：行隐藏、高度自适应（<=70）、按钮变为 +
    w.toggle()
    app.processEvents()
    print("collapsed w/h:", w.width(), w.height())
    print("collapse_btn text:", w.collapse_btn.text())
    assert w.width() == 210
    assert w.height() <= 70, f"折叠高度 {w.height()} 应 <=70"
    assert w.collapse_btn.text() == "+"
    hidden = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            hidden.append(row.isVisible())
    assert not any(hidden), f"折叠态行应全部隐藏，实际 {hidden}"

    # 再展开：恢复正常
    w.toggle()
    app.processEvents()
    print("re-expanded w/h:", w.width(), w.height())
    assert w.collapse_btn.text() == "−"
    assert w.width() == 330
    visible = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            visible.append(row.isVisible())
    assert all(visible), f"展开态行应全部可见，实际 {visible}"

    print("GUI FLOAT SMOKE OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)
