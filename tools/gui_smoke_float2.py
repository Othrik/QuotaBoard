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
    # 每个圈按自身百分比定色：76/96 绿；47 黄；16 红
    assert donuts[0]._color == "#34C724" and donuts[1]._color == "#34C724", \
        [d._color for d in donuts]
    assert donuts[2]._color == "#FAAD14", donuts[2]._color   # 5h 47% → 黄
    assert donuts[3]._color == "#F5222D", donuts[3]._color   # 周 16% → 红
    print("donut colors:", [d._color for d in donuts])
    print("expanded w/h:", w.width(), w.height())
    assert w.width() == 330

    # 折叠态：行隐藏、高度自适应（<=70）
    w.toggle()
    app.processEvents()
    print("collapsed w/h:", w.width(), w.height())
    assert w.width() == 210
    assert w.height() <= 70, f"折叠高度 {w.height()} 应 <=70"
    # 折叠态头部右侧显示正在使用的 AI 图标（codex=ChatGPT、doubao 共 2 个）
    head_logos = []
    for i in range(w.head_logos.count()):
        item = w.head_logos.itemAt(i)
        ww = item.widget()
        if ww is not None:
            head_logos.append(ww)
    print("head logos:", len(head_logos))
    assert len(head_logos) == 2, f"折叠态头部应有 2 个 AI 图标，实际 {len(head_logos)}"
    hidden = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            hidden.append(row.isVisible())
    assert not any(hidden), f"折叠态行应全部隐藏，实际 {hidden}"

    # 折叠态点击头部 → 展开（无 +/- 按钮，直接点击切换）
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF, QEvent, Qt
    hc = w.header.rect().center()
    hg = w.header.mapToGlobal(hc)
    ev_p = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(hc),
                       QPointF(hg), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    ev_r = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(hc),
                       QPointF(hg), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    w.mousePressEvent(ev_p)
    w.mouseReleaseEvent(ev_r)
    app.processEvents()
    print("re-expanded w/h:", w.width(), w.height())
    assert w.width() == 330, f"点击头部应展开，实际宽 {w.width()}"
    visible = []
    for i in range(w.body.count()):
        row = w.body.itemAt(i).widget()
        if row is not None:
            visible.append(row.isVisible())
    assert all(visible), f"展开态行应全部可见，实际 {visible}"
    assert w.expanded is True

    # 展开态点击头部 → 收起
    ev_p2 = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(hc),
                        QPointF(hg), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    ev_r2 = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(hc),
                        QPointF(hg), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    w.mousePressEvent(ev_p2)
    w.mouseReleaseEvent(ev_r2)
    app.processEvents()
    print("collapsed again w/h:", w.width(), w.height())
    assert w.width() == 210 and w.expanded is False

    print("GUI FLOAT SMOKE OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)
