"""悬浮窗主界面：无边框、置顶、半透明、可拖动、折叠/展开。"""
from __future__ import annotations

import os
from html import escape
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPoint, QRectF, Qt, Signal, QEvent, QTimer
from PySide6.QtGui import (
    QAction, QColor, QFont, QGuiApplication, QIcon, QImage, QPainter, QPen,
    QPixmap, QPalette, QCursor,
)
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QScrollArea, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QMenu, QToolTip, QPushButton, QProgressBar, QVBoxLayout, QWidget,
)

from ..config import Config
from ..model import QuotaResult
from ..typography import typography
from ..scheduler import Scheduler

C_GREEN = "#27AE80"
C_YELLOW = "#E5A132"
C_RED = "#E45D6A"
C_BLUE = "#1677FF"
C_GRAY = "#8A9099"
TEXT_MAIN = "#1F2329"
TEXT_SUB = "#646A73"
SNAP_THRESHOLD = 24  # 距屏幕边缘多少像素内触发吸顶吸附

# 平台 → 行首 Logo 文件（assets/logo/ 下，随 exe 一起打包）
PLATFORM_LOGO = {
    "openai": "openai.png",
    # ChatGPT（ChatGPT Plus / Codex）全部使用 OpenAI 官方图标
    "chatgpt_plus": "openai.png",
    "codex": "openai.png",
    "dmxapi": "dmxapi.png",
    "gemini": "gemini.png",
    "doubao": "doubao.png",
    "zhipu": "zhipu-glm.png",
    "zhipu_member": "zhipu.png",
    "kimi": "kimi.png",
    "deepseek": "deepseek.png",
    "volc": "volc.png",
}


def _resource_path(rel: str) -> str:
    """定位资源文件：打包后取 sys._MEIPASS，开发时取项目根目录。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base) / rel)
    return str(Path(__file__).resolve().parent.parent.parent / rel)


def _pct_color(pct: float) -> str:
    """按剩余百分比定色：≥75 绿、<30 红、中间黄（单圈自身颜色）。"""
    if pct < 30:
        return C_RED
    if pct < 75:
        return C_YELLOW
    return C_GREEN


def _logo_effective_ratio(pix: QPixmap) -> float:
    """统计图片不透明像素面积占比（有效像素密度），用于图标视觉大小对齐。"""
    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()
    if w <= 0 or h <= 0:
        return 1.0
    bits = img.constBits()
    stride = img.bytesPerLine()
    opaque = 0
    total = w * h
    for y in range(h):
        base = y * stride
        for x in range(w):
            if bits[base + x * 4 + 3] > 16:
                opaque += 1
    return opaque / total if total else 1.0


def _platform_logo(platform: str, size: int = 18) -> Optional[QLabel]:
    """返回平台 Logo 小图（默认 18px 逻辑尺寸）。

    - 高分屏按设备像素比渲染，避免模糊；
    - 按「有效像素面积占比」对齐视觉大小（以 openai/ChatGPT 图标为基准）：
      填充密实的大图标缩小、细线留白多的小图标保持，使各 Logo 视觉上大小一致。
    """
    name = PLATFORM_LOGO.get(platform)
    if not name:
        return None
    path = _resource_path(f"assets/logo/{name}")
    if not os.path.isfile(path):
        return None
    pix = QPixmap(path)
    if pix.isNull():
        return None
    ratio = _logo_effective_ratio(pix)
    # 基准占比取 openai.png（ChatGPT 图标）；找不到时回退 0.38
    base = 0.38
    base_path = _resource_path("assets/logo/openai.png")
    if os.path.isfile(base_path):
        bp = QPixmap(base_path)
        if not bp.isNull():
            base = _logo_effective_ratio(bp)
    # 面积对齐 scale；为免实心圆头像类图标缩得过小看不清，
    # 采用半程对齐（压缩幅度减半），并保底 0.9（各图标落在 16-18px 区间）。
    # 豆包使用用户裁剪的官方头像，直接与 ChatGPT 同尺寸显示（18px）。
    area_scale = (base / ratio) ** 0.5 if ratio > 0 else 1.0
    scale = max(0.9, 1.0 + (area_scale - 1.0) * 0.5)
    if platform == "doubao":
        scale = 1.0
    lab = QLabel()
    lab.setFixedSize(size, size)
    # 设备像素比感知：pixmap 按 dpr 放大渲染，QLabel 逻辑尺寸不变，高分屏下不糊
    dpr = 1.0
    scr = QGuiApplication.primaryScreen()
    if scr is not None:
        dpr = max(1.0, scr.devicePixelRatio())
    px = max(1, int(round(size * scale * dpr)))
    scaled = pix.scaled(
        px, px, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(dpr)
    lab.setPixmap(scaled)
    return lab


def _row_level(result: QuotaResult) -> str:
    """行状态等级：有多窗口（ChatGPT / 豆包）时按「周」额度判定，
    其余平台按整体剩余百分比。规则：≥75% ok(绿)、<30% danger(红)、中间 warn(黄)。"""
    if not result.ok:
        return "danger"
    pct = result.percent
    if result.metrics:
        for m in result.metrics:
            if m.get("label") == "周":
                try:
                    pct = float(m.get("percent"))
                except (TypeError, ValueError):
                    pass
                break
    if pct is None:
        return "ok"
    if pct < 30:
        return "danger"
    if pct < 75:
        return "warn"
    return "ok"


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
    """环形图：外圈进度环 + 中心百分比 + 底部标签。
    圈体较小、条带两端圆头、底部标签与圈保持间距。"""

    def __init__(self, percent: float, color: str, label: str = "", font_family="Microsoft YaHei UI", font_weight=700) -> None:
        super().__init__()
        self._pct = max(0.0, min(100.0, float(percent)))
        self._color = color
        self._label = label
        self._font_family = font_family
        self._font_weight = font_weight
        # 高 55：标签区底部落在 widget 内，避免「5h / 周」下沿被裁
        self.setFixedSize(46, 55)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QRectF(6, 3, 34, 34)
        # 底环
        p.setPen(QPen(QColor("#EEF0F2"), 5))
        p.drawEllipse(ring)
        # 进度环：圆头端点（RoundCap）使条带两端圆润
        pen = QPen(QColor(self._color), 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        # 从顶部（90°）逆时针画剩余比例
        p.drawArc(ring, 90 * 16, int(-self._pct * 3.6 * 16))
        f = QFont(self._font_family)
        f.setPointSize(8)
        f.setWeight(QFont.Weight(self._font_weight))
        p.setFont(f)
        p.setPen(QColor(TEXT_MAIN))
        p.drawText(ring, Qt.AlignmentFlag.AlignCenter, f"{self._pct:.0f}%")
        if self._label:
            f2 = QFont(self._font_family)
            f2.setWeight(QFont.Weight(self._font_weight))
            f2.setPointSize(8)
            p.setFont(f2)
            p.setPen(QColor(TEXT_SUB))
            # 标签与圈底保持间距，避免贴太近
            p.drawText(QRectF(0, 43, 46, 10), Qt.AlignmentFlag.AlignCenter,
                       self._label)
        p.end()


class _Row(QFrame):
    """单平台额度行。"""

    def __init__(self, result: QuotaResult, manual: bool = False, typography_options=None) -> None:
        super().__init__()
        self.setObjectName("row")
        self.setStyleSheet(
            "#row { background: rgba(248,250,253,0.95); border-radius: 10px; }"
            "#row:hover { background: rgba(245,247,250,0.9); }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)

        level = _row_level(result)
        color = C_GREEN if level == "ok" else (C_YELLOW if level == "warn" else C_RED)
        if manual:
            color = C_BLUE
        # 行首：平台 Logo（无 Logo 的平台不加，替代原状态色点）
        logo = _platform_logo(result.platform)
        if logo is not None:
            lay.addWidget(logo)

        left = QVBoxLayout()
        left.setSpacing(3)
        left.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        style = typography(typography_options)
        name = QLabel(result.label)
        name.setStyleSheet(f"font-family:'{style['family']}';font-size:{style['name_size']+2}px;font-weight:{style['weight']};color:{TEXT_MAIN};")
        sub = result.updated_at.rsplit(" ", 1)[-1]
        if result.error:
            sub = f"失败：{result.error}"
        elif result.metrics:
            notes = result.sub_note + " " + " ".join(str(m.get("note", "")) for m in result.metrics)
            reset_5h = re.search(r"5h\s*重置\s*(\d{1,2}:\d{2})", notes, re.IGNORECASE)
            reset_week = re.search(r"周\s*重置\s*(\d{2}-\d{2})", notes)
            parts = []
            if reset_5h:
                parts.append(f"5h重置 {reset_5h.group(1)}")
            if reset_week:
                parts.append(f"周重置 {reset_week.group(1)}")
            sub = " · ".join(parts)
        note = QLabel(sub)
        note.setStyleSheet(f"font-size: 11px; color: {TEXT_SUB};")
        note.setWordWrap(False)
        note.setMaximumWidth(170)
        note.setToolTip(sub)
        left.addWidget(name)
        left.addWidget(note)
        note.setVisible(bool(sub))
        lay.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        if result.metrics:
            # 多窗口环形图（如 ChatGPT 5h / 周）：每个圈按自身剩余百分比定色
            donuts = QHBoxLayout()
            donuts.setSpacing(4)
            for m in result.metrics:
                try:
                    m_pct = float(m.get("percent"))
                except (TypeError, ValueError):
                    m_pct = 0.0
                donuts.addWidget(_Donut(m_pct, _pct_color(m_pct),
                                        str(m.get("label", "")), font_family=style["quota_family"], font_weight=style["quota_weight"]))
            right.addLayout(donuts)
        else:
            val = QLabel(result.display if result.ok else "—")
            val.setStyleSheet(f"font-family:'{style['quota_family']}';font-size:{style['quota_size']+2}px;font-weight:{style['quota_weight']};color:{TEXT_MAIN};")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            right.addWidget(val)

            # 无法计算百分比（percent=None，如积分/余额）时只显示数字，不画条带
            if result.percent is not None:
                bar = QProgressBar()
                bar.setFixedHeight(5)
                bar.setTextVisible(False)
                pct = int(round(result.percent))
                bar.setRange(0, 100)
                bar.setValue(max(0, min(100, pct)))
                bar.setStyleSheet(
                    f"QProgressBar {{ background: #EEF0F2; border: none; border-radius: 3px; }}"
                    f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}")
                right.addWidget(bar)
        lay.addLayout(right, 0)

        tip = (f"{result.label}\n剩余：{result.display}\n"
               f"更新时间：{result.updated_at}")
        if result.sub_note:
            tip += f"\n{result.sub_note}"
        if result.error:
            tip += f"\n错误：{result.error}"
        self.setToolTip(tip)


def _dock_quota_text(result: QuotaResult, font_weight: int = 700) -> str:
    def red(text):
        return f'<span style="color:{C_RED}; font-weight:{font_weight}">{escape(text)}</span>'
    if not result.ok:
        return red("请求失败")
    if not result.metrics:
        text = escape(result.display)
        if result.percent is not None:
            text = re.sub(r"-?\d+(?:\.\d+)?%", lambda m: f'<span style="color:{_pct_color(result.percent)}; font-weight:{font_weight}">{m.group(0)}</span>', text)
        return text
    metrics = []
    for metric in result.metrics:
        try:
            pct = float(metric.get("percent"))
        except (TypeError, ValueError):
            continue
        metrics.append((metric, pct))
    for metric, pct in metrics:
        if metric.get("label") == "周" and pct <= 0:
            notes = str(metric.get("note", "")) + " " + result.sub_note
            date = re.search(r"周\s*重置\s*(?:\d{4}-)?(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}:\d{2}))?", notes)
            if date:
                clock = f" {date[3]} " if date[3] else " "
                return red(f"{int(date[1])}月{int(date[2])}日{clock}周重置")
            return red("周额度用完，等待重置")
    parts = []
    for metric, pct in metrics:
        label = str(metric.get("label", ""))
        if label == "5h" and pct <= 0:
            notes = str(metric.get("note", "")) + " " + result.sub_note
            time = re.search(r"5h\s*重置\s*(\d{1,2}:\d{2})", notes, re.I)
            parts.append(red(f"5h {time[1]}重置" if time else "5h 等待重置"))
        else:
            parts.append(f'{escape(label)} <span style="color:{_pct_color(pct)}; font-weight:{font_weight}">{pct:.0f}%</span>')
    return " · ".join(parts)


def _quota_details(result: QuotaResult, include_title: bool = True, font_weight: int = 700, table_width: int = 260) -> str:
    rows = []
    def row(label, value, color="#111111", bold=False):
        weight = f"font-weight:{font_weight};" if bold else ""
        rows.append(f'<tr><td style="color:#111111;padding:4px 16px 4px 0;">{escape(label)}</td><td align="right" style="padding:4px 0;color:{color};{weight}">{escape(str(value))}</td></tr>')
    if not result.ok:
        row("查询状态", "暂时无法获取", "#111111", True)
        rows.append(f'<tr><td colspan="2" style="color:#111111;padding:6px 0;">{escape(result.error)}</td></tr>')
    elif result.metrics:
        for metric in result.metrics:
            try:
                pct = float(metric['percent'])
            except (KeyError, TypeError, ValueError):
                continue
            label = str(metric.get('label', ''))
            row("5 小时剩余" if label == '5h' else "每周剩余" if label == '周' else label, f"{pct:.0f}%", "#111111", True)
            note = str(metric.get('note', ''))
            reset = re.sub(r"^(?:5h|周)重置\s*", "", note)
            if reset:
                row("重置时间", reset)
    else:
        row("当前余额", result.display, "#111111", True)
        if result.total is not None:
            row("总量", f"{result.total:,.2f} {result.unit}")
        if result.used is not None:
            row("已用", f"{result.used:,.2f} {result.unit}")
    if result.sub_note and not result.metrics:
        row("说明", result.sub_note)
    return (f'<qt><table width="{table_width}" cellspacing="0" cellpadding="0">'
            + (f'<tr><td colspan="2" style="padding:0 0 10px;"><b>{escape(result.label)}</b></td></tr>' if include_title else '')
            + ''.join(rows) +
            f'<tr><td colspan="2" style="padding:12px 0 0;color:#111111;font-size:10px;">刷新时间 · {escape(result.updated_at)}</td></tr></table></qt>')


class _QuotaPopup(QWidget):
    """Opaque, explicitly painted card; never delegates to native tooltips."""
    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setStyleSheet("background: transparent; color: #111111; font-size: 12px; border: none;")
        layout.addWidget(self.text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        painter.setPen(QColor("#DDE3EB"))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def present(self, text, position):
        self.text.setText(text)
        self.adjustSize()
        screen = QGuiApplication.screenAt(position) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = max(geo.left(), min(position.x(), geo.right() - self.width() + 1))
        y = position.y() + 16
        if y + self.height() > geo.bottom():
            y = position.y() - self.height() - 12
        self.move(x, max(geo.top(), y))
        self.show()
        self.raise_()


class FloatingWindow(QWidget):
    refresh_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, config: Config, scheduler: Scheduler) -> None:
        super().__init__()
        self.config = config
        self.scheduler = scheduler
        self._dock_edge = None
        self._native_mode_previous = bool(config._data.get("taskbar_mode", False))
        self._dock_rows = []
        self.expanded = True
        self._drag_pos: Optional[QPoint] = None
        self._moved = False
        self._results: dict[str, QuotaResult] = {}
        self._last_refresh: Optional[str] = None  # 最近一次刷新时间（HH:MM）

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("QuotaBoard")
        app = QApplication.instance()
        app.setStyleSheet(app.styleSheet() + "\nQToolTip { background-color: #FFFFFF; color: #111111; border: 1px solid #DDE3EB; padding: 14px; font-size: 12px; }")
        tooltip_palette = QPalette()
        tooltip_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
        tooltip_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#111111"))
        QToolTip.setPalette(tooltip_palette)
        self.setWindowIcon(make_app_icon())

        self._hover_popup = _QuotaPopup(self)
        self._build_ui()
        self.apply_shadow()

        self.scheduler.refreshed.connect(self.on_results)
        self.scheduler.result_ready.connect(self.on_partial_result)
        self._anchor_timer = QTimer(self)
        self._anchor_timer.setInterval(1000)
        self._anchor_timer.timeout.connect(self._keep_taskbar_position)
        self._anchor_timer.start()

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
        self.card_lay.setContentsMargins(8, 4, 8, 8)
        self.card_lay.setSpacing(6)

        # 头部（可点击收起/展开）
        self.header = QWidget(self.card)
        self.header.setObjectName("header")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        hlay = QHBoxLayout(self.header)
        hlay.setContentsMargins(10, 4, 10, 4)
        self.head_title = QLabel("AI 额度")
        self.head_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_MAIN};")
        hlay.addWidget(self.head_title)
        hlay.addStretch(1)
        # 头部右侧：正在使用的 AI 图标（折叠态可一眼看到在用哪些平台）
        self.head_logos = QHBoxLayout()
        self.head_logos.setSpacing(6)
        hlay.addLayout(self.head_logos)
        self.head_summary = QLabel("")
        self.head_summary.setStyleSheet(f"font-size: 12px; color: {TEXT_SUB};")
        hlay.addWidget(self.head_summary)
        self.header_buttons = []
        for text, tip, signal in (("刷新", "立即刷新", self.refresh_requested),):
            button = QPushButton(text)
            button.setFixedSize(34, 26)
            button.setToolTip(tip)
            button.setStyleSheet("QPushButton { border: none; border-radius: 6px; color: #667085; font-size: 11px; } QPushButton:hover { background: #EAF0FC; color: #4169E1; }")
            button.clicked.connect(signal.emit)
            hlay.addWidget(button)
            self.header_buttons.append(button)
        # Keep the header compact even when the window retains extra height.
        self.header.setFixedHeight(max(38, self.head_title.fontMetrics().height() + 12))
        self.card_lay.addWidget(self.header)

        # 内容区
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self.card_lay.addLayout(self.body)
        self.dock = QScrollArea(self.card)
        self.dock.setFrameShape(QFrame.Shape.NoFrame)
        self.dock.setWidgetResizable(True)
        self.dock.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.dock_content = QWidget()
        self.dock_content.setStyleSheet("background: transparent;")
        self.dock_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.dock_content)
        self.dock_layout.setContentsMargins(10, 5, 10, 5)
        self.dock_layout.setSpacing(14)
        self.dock.setWidget(self.dock_content)
        self.card_lay.addWidget(self.dock)
        self.dock.hide()

    def apply_shadow(self) -> None:
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28)
        sh.setOffset(0, 6)
        sh.setColor(QColor(31, 35, 41, 64))
        self.card.setGraphicsEffect(sh)

    # ---------- 数据 ----------
    def on_partial_result(self, key, result):
        self._results[key] = result
        self.render()

    def on_results(self, results: dict[str, QuotaResult]) -> None:
        self._results = results
        self._last_refresh = datetime.now().strftime("%H:%M")
        self.render()

    def render(self) -> None:
        native_mode = bool(self.config._data.get("taskbar_mode", False))
        if native_mode != self._native_mode_previous:
            self._native_mode_previous = native_mode
            self.hide() if native_mode else self.show()
        # 清空旧行
        while self.body.count():
            item = self.body.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        rows: list[QuotaResult] = []
        for key in self.config.platform_order:
            if not self.config.is_enabled(key):
                continue
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

        from ..taskbar_snapshot import export_snapshot
        export_snapshot(self.config, rows)
        if hasattr(self, "native_taskbar"):
            self.native_taskbar.set_rows(rows)

        if not rows:
            tip = QLabel("尚未配置平台：右键 → 设置")
            tip.setStyleSheet(f"font-size: 13px; color: {TEXT_SUB}; padding: 10px 14px;")
            self.body.addWidget(tip)
        else:
            for r in rows:
                self.body.addWidget(_Row(r, manual=(r.platform == "manual"), typography_options=self.config._data.get("display_typography")))

        # 头部不再显示「N 个偏低/告警/正常」摘要（用户要求移除）
        self.head_summary.setText("")
        # 头部右侧：正在使用的 AI 图标（按展示顺序，取有 Logo 的平台）
        while self.head_logos.count():
            item = self.head_logos.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for r in rows:
            logo = _platform_logo(r.platform, size=16)
            if logo is not None:
                self.head_logos.addWidget(logo)

        self._dock_rows = rows
        self.update_size()

    def update_size(self) -> None:
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.card.graphicsEffect().setEnabled(not bool(self._dock_edge))
        self.header.setVisible(not self._dock_edge)
        self.dock.setVisible(bool(self._dock_edge))
        if self._dock_edge:
            self._update_dock()
            return
        self.layout().setContentsMargins(14, 14, 14, 14)
        self.card_lay.setContentsMargins(*( (8, 4, 8, 8) if self.expanded else (0, 0, 0, 0) ))
        self.card_lay.setSpacing(6 if self.expanded else 0)
        self.header.layout().setContentsMargins(*( (10, 4, 10, 4) if self.expanded else (8, 8, 8, 8) ))
        self.header.layout().setStretch(1, 1 if self.expanded else 0)
        self.header.setFixedHeight(max(38, self.head_title.fontMetrics().height() + 12) if self.expanded else 32)
        self.head_title.setVisible(self.expanded)
        for button in self.header_buttons:
            button.setVisible(self.expanded)
        # 折叠/展开时真正隐藏/显示内容行（QBoxLayout 无 hide，
        # 必须逐个操作子 widget，否则行仍占位导致显示错乱）
        for i in range(self.body.count()):
            w = self.body.itemAt(i).widget()
            if w is not None:
                w.setVisible(self.expanded)
        # 头部右侧的在用 AI 图标：仅折叠态显示（展开态隐藏，避免与内容重复）
        for i in range(self.head_logos.count()):
            w = self.head_logos.itemAt(i).widget()
            if w is not None:
                w.setVisible(not self.expanded)
        # 展开态头部右侧显示最近刷新时间；折叠态隐藏（让位给 AI 图标）
        if self.expanded and self._last_refresh:
            self.head_summary.setText(f"刷新 {self._last_refresh}")
            self.head_summary.setVisible(True)
        else:
            self.head_summary.clear()
            self.head_summary.setVisible(False)

        if self.expanded:
            self.setFixedWidth(380)
            # 解除折叠时的高度限制，让 adjustSize 自适应
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.adjustSize()
        else:
            # 折叠态同样走 adjustSize：body 行已隐藏，窗口自适应为头部高度，
            # 避免固定像素高度在高 DPI / 字体缩放下截断 header
            count = self.head_logos.count()
            self.setFixedWidth(46 + 16 * count + 6 * max(0, count - 1))
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.adjustSize()

    def _update_dock(self) -> None:
        while self.dock_layout.count():
            item = self.dock_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        horizontal = self._dock_edge in ("top", "bottom", "taskbar")
        self.dock_layout.setDirection(QBoxLayout.Direction.LeftToRight if horizontal else QBoxLayout.Direction.TopToBottom)
        for result in self._dock_rows:
            cell = QWidget()
            line = QHBoxLayout(cell)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(6)
            logo = _platform_logo(result.platform, 18)
            if logo:
                line.addWidget(logo)
            else:
                line.addWidget(QLabel(result.label))
            style = typography(self.config._data.get("display_typography"))
            text = _dock_quota_text(result, font_weight=style["weight"])
            value = QLabel(text)
            value.setTextFormat(Qt.TextFormat.RichText)
            value.setStyleSheet(f"font-family:'{style['family']}';font-size:{style['quota_size']}px;font-weight:{style['weight']};color:{TEXT_MAIN if result.ok else C_RED};")
            line.addWidget(value)
            cell.setToolTip(_quota_details(result))
            for child in [cell] + cell.findChildren(QWidget):
                child.setProperty("quotaHover", _quota_details(result))
                child.setToolTip("")
                child.installEventFilter(self)
            self.dock_layout.addWidget(cell)
            cell.show()
        if not self._dock_rows:
            self.dock_layout.addWidget(QLabel("右键设置平台"))
        for i in range(self.body.count()):
            if self.body.itemAt(i).widget():
                self.body.itemAt(i).widget().hide()
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.card_lay.setContentsMargins(0, 0, 0, 0)
        self.card_lay.setSpacing(0)
        self.dock_layout.activate()
        hint = self.dock_content.sizeHint()
        geo = self.screen().availableGeometry()
        if horizontal:
            limit = min(360, geo.width() - 16) if self._dock_edge == "taskbar" else geo.width()
            self.setFixedSize(min(limit, hint.width() + 4), 54 if hint.width() + 4 > limit else 36)
        else:
            self.setFixedSize(hint.width() + 4, min(geo.height(), hint.height() + 4))
        self._anchor_dock()

    def _anchor_dock(self) -> None:
        geo = self.screen().availableGeometry()
        x = max(geo.left(), min(self.x(), geo.right() + 1 - self.width()))
        y = max(geo.top(), min(self.y(), geo.bottom() + 1 - self.height()))
        if self._dock_edge == "top": y = geo.top()
        if self._dock_edge == "bottom": y = geo.bottom() + 1 - self.height()
        if self._dock_edge == "left": x = geo.left()
        if self._dock_edge == "right": x = geo.right() + 1 - self.width()
        if self._dock_edge == "taskbar":
            x = geo.left() + 8
            y = geo.bottom() + 1 - self.height() - 6
        self.move(x, y)

    def _keep_taskbar_position(self):
        if self._dock_edge == "taskbar" and self.isVisible():
            self._anchor_dock()

    def set_taskbar_mode(self, enabled):
        self.config._data["taskbar_mode"] = bool(enabled)
        self.config.save()
        self._dock_edge = None
        self.expanded = True
        self.render()
        self.hide() if enabled else self.show()

    # ---------- 折叠/展开 ----------
    def toggle(self) -> None:
        if self._dock_edge:
            return
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
            if self._dock_edge == "taskbar":
                return
            if self._dock_edge:
                self._dock_edge = None
                self.expanded = True
                self.update_size()
                self._drag_pos = QPoint(self.width() // 2, 24)
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
        distances = {"top": abs(y-top), "bottom": abs(bottom-y-h),
                     "left": abs(x-left), "right": abs(right-x-w)}
        edge = min(distances, key=distances.get)
        self._dock_edge = edge if distances[edge] <= SNAP_THRESHOLD else None
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
                # 点击头部区域：折叠态展开；展开态收起（无 +/- 按钮，直接点击切换）。
                # 折叠态下整个窗口即头部，点击任意位置均展开。
                in_header = (self.expanded
                             and self.header.geometry().contains(self.card.mapFrom(self, event.position().toPoint())))
                if not self.expanded or in_header:
                    self.toggle()
            else:
                # 拖动结束：靠近屏幕边缘时吸顶贴边
                self.move(*self._snap_rect(self.frameGeometry()))
                self.update_size()
            self._drag_pos = None
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched, event):
        details = watched.property("quotaHover")
        if details:
            if event.type() in (QEvent.Type.Enter, QEvent.Type.ToolTip):
                self._hover_popup.present(details, QCursor.pos())
                if event.type() == QEvent.Type.ToolTip:
                    return True
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.Hide):
                self._hover_popup.hide()
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        self._hover_popup.hide()
        super().hideEvent(event)

    def contextMenuEvent(self, event) -> None:
        self._hover_popup.hide()
        menu = QMenu(self)
        taskbar = QAction("任务栏常驻额度", menu)
        taskbar.setCheckable(True)
        taskbar.setChecked(bool(self.config._data.get("taskbar_mode", False)))
        taskbar.toggled.connect(self.set_taskbar_mode)
        menu.addAction(taskbar)
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
