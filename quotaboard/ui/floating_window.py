"""悬浮窗主界面：无边框、置顶、半透明、可拖动、折叠/展开。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QMenu, QProgressBar, QVBoxLayout, QWidget,
)

from ..config import Config
from ..model import QuotaResult
from ..scheduler import Scheduler

C_GREEN = "#34C724"
C_YELLOW = "#FAAD14"
C_RED = "#F5222D"
C_BLUE = "#1677FF"
C_GRAY = "#8A9099"
TEXT_MAIN = "#1F2329"
TEXT_SUB = "#646A73"
SNAP_THRESHOLD = 24  # 距屏幕边缘多少像素内触发吸顶吸附


def make_app_icon() -> QIcon:
    """程序图标：蓝底圆角方块 + 白色刻度条（象征额度）。"""
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3370FF"))
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setBrush(QColor("#FFFFFF"))
    for i, h in enumerate((14, 26, 36, 22)):
        x = 14 + i * 10
        p.drawRoundedRect(x, 48 - h, 6, h, 3, 3)
    p.end()
    return QIcon(pix)


class _StatusDot(QLabel):
    def __init__(self, color: str, size: int = 10) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self.setColor(color)

    def setColor(self, color: str) -> None:
        self.setStyleSheet(
            f"background-color: {color}; border-radius: {self.width() // 2}px;")


class _Donut(QWidget):
    """环形图：外圈进度环 + 中心百分比 + 底部标签。"""

    def __init__(self, percent: float, color: str, label: str = "") -> None:
        super().__init__()
        self._pct = max(0.0, min(100.0, float(percent)))
        self._color = color
        self._label = label
        self.setFixedSize(50, 56)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QRectF(5, 4, 40, 40)
        p.setPen(QPen(QColor("#EEF0F2"), 5))
        p.drawEllipse(ring)
        p.setPen(QPen(QColor(self._color), 5))
        # 从顶部（90°）逆时针画剩余比例
        p.drawArc(ring, 90 * 16, int(-self._pct * 3.6 * 16))
        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT_MAIN))
        p.drawText(ring, Qt.AlignmentFlag.AlignCenter, f"{self._pct:.0f}%")
        if self._label:
            f2 = QFont()
            f2.setPointSize(8)
            p.setFont(f2)
            p.setPen(QColor(TEXT_SUB))
            p.drawText(QRectF(0, 46, 50, 10), Qt.AlignmentFlag.AlignCenter,
                       self._label)
        p.end()


class _Row(QFrame):
    """单平台额度行。"""

    def __init__(self, result: QuotaResult, manual: bool = False) -> None:
        super().__init__()
        self.setObjectName("row")
        self.setStyleSheet(
            "#row { background: rgba(255,255,255,0.55); border-radius: 10px; }"
            "#row:hover { background: rgba(245,247,250,0.9); }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        level = result.status_level()
        color = C_GREEN if level == "ok" else (C_YELLOW if level == "warn" else C_RED)
        if manual:
            color = C_BLUE
        self.dot = _StatusDot(color)
        lay.addWidget(self.dot)

        left = QVBoxLayout()
        left.setSpacing(2)
        name = QLabel(result.label)
        name.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_MAIN};")
        sub = f"{result.unit} · {result.updated_at}" if result.unit else result.updated_at
        if result.error:
            sub = f"失败：{result.error}"
        elif result.sub_note:
            sub = f"{result.sub_note} · {result.updated_at}"
        elif result.total is not None and result.used is not None:
            sub = f"已用 {result.used:,.0f} / {result.total:,.0f} {result.unit} · {result.updated_at}"
        note = QLabel(sub)
        note.setStyleSheet(f"font-size: 11px; color: {TEXT_SUB};")
        note.setWordWrap(False)
        left.addWidget(name)
        left.addWidget(note)
        lay.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        if result.metrics:
            # 多窗口环形图（如 ChatGPT 5h / 周）
            donuts = QHBoxLayout()
            donuts.setSpacing(4)
            for m in result.metrics:
                try:
                    m_pct = float(m.get("percent"))
                except (TypeError, ValueError):
                    m_pct = 0.0
                donuts.addWidget(_Donut(m_pct, color, str(m.get("label", ""))))
            right.addLayout(donuts)
        else:
            val = QLabel(result.display if result.ok else "—")
            val.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_MAIN};")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            right.addWidget(val)

            bar = QProgressBar()
            bar.setFixedHeight(5)
            bar.setTextVisible(False)
            pct = int(round(result.percent)) if result.percent is not None else 0
            bar.setRange(0, 100)
            bar.setValue(max(0, min(100, pct)))
            bar.setStyleSheet(
                f"QProgressBar {{ background: #EEF0F2; border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}")
            right.addWidget(bar)
        lay.addLayout(right, 0)

        self.setToolTip(
            f"{result.label}\n剩余：{result.display}\n"
            f"更新时间：{result.updated_at}"
            + (f"\n错误：{result.error}" if result.error else ""))


class FloatingWindow(QWidget):
    refresh_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, config: Config, scheduler: Scheduler) -> None:
        super().__init__()
        self.config = config
        self.scheduler = scheduler
        self.expanded = True
        self._drag_pos: Optional[QPoint] = None
        self._moved = False
        self._results: dict[str, QuotaResult] = {}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("QuotaBoard")
        self.setWindowIcon(make_app_icon())

        self._build_ui()
        self.apply_shadow()

        self.scheduler.refreshed.connect(self.on_results)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        self.card = QFrame(self)
        self.card.setObjectName("card")
        self.card.setStyleSheet(
            "#card { background: rgba(255,255,255,0.92); border: 1px solid rgba(255,255,255,0.65);"
            " border-radius: 16px; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.addWidget(self.card)

        self.card_lay = QVBoxLayout(self.card)
        self.card_lay.setContentsMargins(0, 0, 0, 0)
        self.card_lay.setSpacing(6)

        # 头部（可点击收起）
        self.header = QWidget(self.card)
        self.header.setObjectName("header")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        hlay = QHBoxLayout(self.header)
        hlay.setContentsMargins(14, 10, 14, 6)
        self.head_dot = _StatusDot(C_GRAY, 8)
        hlay.addWidget(self.head_dot)
        self.head_title = QLabel("AI 额度")
        self.head_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_MAIN};")
        hlay.addWidget(self.head_title)
        hlay.addStretch(1)
        self.head_summary = QLabel("")
        self.head_summary.setStyleSheet(f"font-size: 12px; color: {TEXT_SUB};")
        hlay.addWidget(self.head_summary)
        self.collapse_btn = QLabel("−")
        self.collapse_btn.setStyleSheet(
            f"font-size: 16px; color: {TEXT_SUB}; padding: 0 6px;")
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hlay.addWidget(self.collapse_btn)
        self.card_lay.addWidget(self.header)

        # 内容区
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self.card_lay.addLayout(self.body)

    def apply_shadow(self) -> None:
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28)
        sh.setOffset(0, 6)
        sh.setColor(QColor(31, 35, 41, 64))
        self.card.setGraphicsEffect(sh)

    # ---------- 数据 ----------
    def on_results(self, results: dict[str, QuotaResult]) -> None:
        self._results = results
        self.render()

    def render(self) -> None:
        # 清空旧行
        while self.body.count():
            item = self.body.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        rows: list[QuotaResult] = []
        for key in ("openai", "chatgpt_plus", "codex", "doubao",
                    "zhipu", "zhipu_member", "kimi", "volc"):
            r = self._results.get(key)
            if r is not None:
                rows.append(r)
            elif self.config.is_enabled(key):
                cached = self.config.get_cache(key)
                if cached:
                    try:
                        rows.append(QuotaResult(**cached))
                    except TypeError:
                        pass

        # 手动条目
        for name, entry in self.config.manual_entries.items():
            try:
                total = float(entry.get("total", 0) or 0)
                used = float(entry.get("used", 0) or 0)
            except (TypeError, ValueError):
                total = used = 0.0
            unit = str(entry.get("unit", "") or "")
            pct = (total - used) / total * 100 if total > 0 else None
            rows.append(QuotaResult(
                platform="manual", label=name,
                display=f"{total - used:,.0f}" if pct is not None else "—",
                available=max(0.0, total - used), total=total, used=used,
                unit=unit, percent=pct, ok=True))

        if not rows:
            tip = QLabel("尚未配置平台：右键 → 设置")
            tip.setStyleSheet(f"font-size: 13px; color: {TEXT_SUB}; padding: 10px 14px;")
            self.body.addWidget(tip)
        else:
            for r in rows:
                self.body.addWidget(_Row(r, manual=(r.platform == "manual")))

        # 头部摘要
        n_ok = sum(1 for r in rows if r.status_level() == "ok")
        n_warn = sum(1 for r in rows if r.status_level() == "warn")
        n_danger = sum(1 for r in rows if r.status_level() == "danger")
        if rows:
            if n_danger:
                self.head_dot.setColor(C_RED)
                self.head_summary.setText(f"{n_danger} 个告警")
            elif n_warn:
                self.head_dot.setColor(C_YELLOW)
                self.head_summary.setText(f"{n_warn} 个偏低")
            else:
                self.head_dot.setColor(C_GREEN)
                self.head_summary.setText(f"{len(rows)} 个正常")
        else:
            self.head_dot.setColor(C_GRAY)
            self.head_summary.setText("未配置")

        self.update_size()

    def update_size(self) -> None:
        # 折叠/展开时真正隐藏/显示内容行（QBoxLayout 无 hide，
        # 必须逐个操作子 widget，否则行仍占位导致显示错乱）
        for i in range(self.body.count()):
            w = self.body.itemAt(i).widget()
            if w is not None:
                w.setVisible(self.expanded)

        if self.expanded:
            self.setFixedWidth(330)
            # 解除折叠时的高度限制，让 adjustSize 自适应
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.adjustSize()
            self.collapse_btn.setText("−")
        else:
            # 折叠态同样走 adjustSize：body 行已隐藏，窗口自适应为头部高度，
            # 避免固定像素高度在高 DPI / 字体缩放下截断 header
            self.setFixedWidth(210)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.adjustSize()
            self.collapse_btn.setText("+")

    # ---------- 折叠/展开 ----------
    def toggle(self) -> None:
        self.expanded = not self.expanded
        self.update_size()

    # ---------- 鼠标交互 ----------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._moved = True
        super().mouseMoveEvent(event)

    def _snap_rect(self, rect) -> tuple[int, int]:
        """吸顶：窗口拖动到屏幕边缘附近时，自动吸附贴齐对应边缘，返回新位置 (x, y)。"""
        screen = self.screen()
        if screen is None:
            return rect.x(), rect.y()
        geo = screen.availableGeometry()
        x, y = rect.x(), rect.y()
        w, h = rect.width(), rect.height()
        left, top = geo.left(), geo.top()
        right, bottom = geo.right() + 1, geo.bottom() + 1
        if abs(x - left) <= SNAP_THRESHOLD:
            x = left
        elif abs(right - (x + w)) <= SNAP_THRESHOLD:
            x = right - w
        if abs(y - top) <= SNAP_THRESHOLD:
            y = top
        elif abs(bottom - (y + h)) <= SNAP_THRESHOLD:
            y = bottom - h
        return x, y

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._moved:
                # 点击头部/折叠按钮：折叠态切换；展开态点头部收起
                if not self.expanded:
                    self.toggle()
                elif self.collapse_btn.underMouse() or self.header.underMouse():
                    self.toggle()
            else:
                # 拖动结束：靠近屏幕边缘时吸顶贴边
                self.move(*self._snap_rect(self.frameGeometry()))
            self._drag_pos = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        act_refresh = QAction("立即刷新", self)
        act_refresh.triggered.connect(self.refresh_requested)
        act_settings = QAction("设置…", self)
        act_settings.triggered.connect(self.settings_requested)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.quit_requested)
        menu.addAction(act_refresh)
        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction(act_quit)
        menu.exec(event.globalPos())
