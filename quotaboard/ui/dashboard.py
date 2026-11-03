"""A persistent quota overview; preferences live behind its Settings button."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget)
from ..model import PLATFORM_META, QuotaResult
from .floating_window import _platform_logo, _pct_color, make_app_icon
from .settings_dialog import SettingsDialog

STYLE = '''
QDialog#overview {background:#F4F6FA;color:#202938;font-family:'Microsoft YaHei UI';font-size:12px;}
QLabel {color:#202938;background:transparent;}
QLabel#eyebrow {color:#708097;font-size:11px;}
QLabel#hero {font-size:27px;font-weight:700;}
QLabel#muted {color:#7B8799;font-size:11px;}
QFrame#quotaCard {background:white;border:1px solid #E3E8F0;border-radius:14px;}
QFrame#summary {background:#E9EFFB;border-radius:12px;}
QPushButton {background:white;color:#44546C;border:1px solid #DAE2EE;border-radius:8px;padding:8px 16px;}
QPushButton:hover {background:#EEF3FE;border-color:#9EB5EB;}
QPushButton#primary {background:#416BDD;color:white;border:none;font-weight:600;}
QPushButton:disabled {background:#E4E9F1;color:#8B98AA;}
QLineEdit,QComboBox {background:white;border:1px solid #DFE5EF;border-radius:8px;padding:7px 10px;color:#44546C;}
QScrollArea {background:transparent;border:none;}
QScrollBar:vertical {width:6px;background:transparent;}
QScrollBar::handle:vertical {background:#CDD7E5;border-radius:3px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
'''


def label(text='', name=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    if name:
        widget.setObjectName(name)
    return widget


def needs_attention(result):
    if not result:
        return False
    if result.status_level() != 'ok':
        return True
    for metric in result.metrics or []:
        try:
            if float(metric.get('percent')) < 75:
                return True
        except (TypeError, ValueError):
            pass
    return False


class QuotaCard(QFrame):
    configure = Signal(str)

    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName('quotaCard')
        self.setMinimumWidth(270)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        icon = _platform_logo(key, 28)
        if icon:
            header.addWidget(icon)
        title = label(PLATFORM_META[key]['label'])
        title.setStyleSheet('font-size:16px;font-weight:700;')
        header.addWidget(title)
        header.addStretch()
        self.status = label()
        header.addWidget(self.status)
        layout.addLayout(header)
        self.value = label()
        self.value.setStyleSheet('font-size:26px;font-weight:700;')
        layout.addWidget(self.value)
        self.metric_rows = []
        for _ in range(4):
            widget = QWidget(self)
            group = QVBoxLayout(widget)
            group.setContentsMargins(0, 0, 0, 0)
            group.setSpacing(5)
            row = QHBoxLayout()
            name, amount = label(), label()
            amount.setStyleSheet('font-size:15px;font-weight:700;')
            row.addWidget(name)
            row.addStretch()
            row.addWidget(amount)
            group.addLayout(row)
            bar = QProgressBar(widget)
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            group.addWidget(bar)
            layout.addWidget(widget)
            self.metric_rows.append((widget, name, amount, bar))
        self.note = label('', 'muted')
        self.note.setWordWrap(True)
        self.note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.note)
        layout.addStretch()
        footer = QHBoxLayout()
        self.timestamp = label('', 'muted')
        footer.addWidget(self.timestamp)
        footer.addStretch()
        self.config_button = QPushButton('配置')
        self.config_button.setStyleSheet('padding:3px 9px;font-size:11px;')
        self.config_button.clicked.connect(lambda: self.configure.emit(key))
        footer.addWidget(self.config_button)
        layout.addLayout(footer)

    def update_result(self, result, enabled):
        success = enabled and result is not None and result.ok
        self.status.setText('未启用' if not enabled else '等待刷新' if result is None else '已更新' if success else '请求失败')
        self.status.setStyleSheet('font-size:11px;color:' + ('#18966C' if success else '#D85E64' if enabled and result else '#8B98AA') + ';')
        metrics = (result.metrics or []) if success else []
        if success and not metrics and result.percent is not None:
            metrics = [dict(label='剩余额度', percent=result.percent)]
        self.value.setVisible(not (success and result.metrics))
        self.value.setText(result.display if success else '—' if enabled else '尚未接入')
        notes = []
        for index, (widget, name, amount, bar) in enumerate(self.metric_rows):
            widget.setVisible(index < len(metrics))
            if index >= len(metrics):
                continue
            metric = metrics[index]
            metric_name = str(metric.get('label', '剩余额度'))
            name.setText(metric_name if '剩余' in metric_name else metric_name + ' 剩余')
            try:
                percent = max(0, min(100, float(metric.get('percent', 0))))
            except (ValueError, TypeError):
                percent = 0
            color = _pct_color(percent)
            amount.setText(f'{percent:g}%')
            amount.setStyleSheet(f'font-size:15px;font-weight:700;color:{color};')
            bar.setValue(round(percent))
            bar.setStyleSheet(f'QProgressBar {{background:#EDF1F6;border:none;border-radius:2px;}} QProgressBar::chunk {{background:{color};border-radius:2px;}}')
            note = str(metric.get('note', '')).strip()
            if note:
                notes.append(note)
        if not enabled:
            note = '在设置中启用此平台，即可在这里查看额度。'
        elif result is None:
            note = '首次查询完成后，将自动显示额度。'
        elif not result.ok:
            note = result.error or '查询失败，下一轮刷新将自动重试。'
        else:
            note = ' · '.join(dict.fromkeys([s for s in [result.sub_note, *notes] if s]))
        self.note.setText(note)
        self.note.setVisible(bool(note))
        self.timestamp.setText('刷新于 ' + result.updated_at if enabled and result else '尚无刷新记录')


class Dashboard(QDialog):
    settings_saved = Signal()

    def __init__(self, config, scheduler):
        super().__init__()
        self.config, self.scheduler = config, scheduler
        self.results = {}
        self.preferences = None
        self.setObjectName('overview')
        self.setWindowTitle('QuotaBoard · 额度总览')
        self.setWindowIcon(make_app_icon())
        self.setStyleSheet(STYLE)
        self.setMinimumSize(660, 460)
        geo = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1000, geo.width()-40), min(780, geo.height()-40))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 18)
        outer.setSpacing(18)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label('QUOTABOARD / OVERVIEW', 'eyebrow'))
        titles.addWidget(label('你的 AI 额度，一目了然', 'hero'))
        titles.addWidget(label('会员额度、积分与 API 余额，集中查看。', 'muted'))
        header.addLayout(titles)
        header.addStretch()
        self.refresh_button = QPushButton('刷新全部')
        self.refresh_button.setObjectName('primary')
        self.refresh_button.clicked.connect(scheduler.refresh_all)
        header.addWidget(self.refresh_button)
        self.settings_button = QPushButton('设置')
        self.settings_button.clicked.connect(lambda: self.open_preferences())
        header.addWidget(self.settings_button)
        outer.addLayout(header)
        summary = QFrame(self)
        summary.setObjectName('summary')
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(20, 14, 20, 14)
        self.summary = label()
        self.summary.setStyleSheet('font-size:13px;font-weight:600;')
        summary_layout.addWidget(self.summary)
        summary_layout.addStretch()
        self.interval = label('', 'muted')
        summary_layout.addWidget(self.interval)
        outer.addWidget(summary)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索应用…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        filters.addWidget(self.search, 1)
        self.filter = QComboBox()
        self.filter.addItems(['全部平台', '已启用', '需要关注'])
        self.filter.currentIndexChanged.connect(self.apply_filter)
        filters.addWidget(self.filter)
        outer.addLayout(filters)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName('dashboardBody')
        body.setStyleSheet('QWidget#dashboardBody {background:transparent;}')
        self.grid = QGridLayout(body)
        self.grid.setContentsMargins(0, 0, 7, 0)
        self.grid.setSpacing(14)
        self.grid.setAlignment(Qt.AlignTop)
        self.cards = {}
        for key in config.platform_order:
            if key not in PLATFORM_META:
                continue
            card = QuotaCard(key, body)
            card.configure.connect(self.open_preferences)
            self.cards[key] = card
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.empty = label('没有匹配的平台。试试其他名称，或在设置中启用应用。', 'muted')
        self.empty.setWordWrap(True)
        outer.addWidget(self.empty)
        footer = label('关闭此面板后，任务栏显示与后台刷新会继续运行。', 'muted')
        outer.addWidget(footer)
        scheduler.result_ready.connect(self.on_result)
        scheduler.refreshed.connect(self.on_results)
        scheduler.refresh_started.connect(self.refresh_started)
        self.reload_config()

    def reload_config(self):
        for key in self.cards:
            if key not in self.results:
                cached = self.config.get_cache(key)
                if cached:
                    try:
                        self.results[key] = QuotaResult(**cached)
                    except (ValueError, TypeError):
                        pass
        self.update_cards()

    def update_cards(self):
        enabled = [key for key in self.cards if self.config.is_enabled(key)]
        successful = sum(bool(self.results.get(k) and self.results[k].ok) for k in enabled)
        attention = sum(needs_attention(self.results.get(k)) for k in enabled)
        self.summary.setText(f'{len(enabled)} 个已启用     /     {successful} 个查询成功     /     {attention} 个需要关注')
        self.interval.setText(f'每 {self.config.refresh_interval_minutes} 分钟自动刷新')
        for key, card in self.cards.items():
            card.update_result(self.results.get(key), self.config.is_enabled(key))
        self.apply_filter()
        self.refresh_button.setEnabled(not self.scheduler.running)
        self.refresh_button.setText('正在刷新…' if self.scheduler.running else '刷新全部')

    def apply_filter(self, *_):
        query = self.search.text().strip().lower()
        visible = []
        for key in self.config.platform_order:
            if key not in self.cards:
                continue
            card = self.cards[key]
            result = self.results.get(key)
            enabled = self.config.is_enabled(key)
            matches = query in (PLATFORM_META[key]['label'] + ' ' + key).lower()
            if self.filter.currentIndex() == 1:
                matches = matches and enabled
            elif self.filter.currentIndex() == 2:
                matches = matches and enabled and needs_attention(result)
            card.setVisible(matches)
            if matches:
                visible.append(card)
        while self.grid.count():
            self.grid.takeAt(0)
        columns = 2 if self.width() >= 760 else 1
        for index, card in enumerate(visible):
            self.grid.addWidget(card, index // columns, index % columns)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if columns == 2 else 0)
        self.empty.setVisible(not visible)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'cards') and hasattr(self, 'empty'):
            self.apply_filter()

    def on_result(self, key, result):
        self.results[key] = result
        self.update_cards()

    def on_results(self, results):
        self.results.update(results)
        self.update_cards()

    def refresh_started(self):
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText('正在刷新…')

    def open_preferences(self, key=None):
        if self.preferences is None:
            self.preferences = SettingsDialog(self.config)
            self.preferences.saved.connect(self._settings_saved)
        if key in self.preferences.nav_items:
            self.preferences.navigation.setCurrentItem(self.preferences.nav_items[key])
        self.preferences.show()
        self.preferences.raise_()
        self.preferences.activateWindow()

    def _settings_saved(self):
        self.reload_config()
        self.settings_saved.emit()

    def present(self):
        self.reload_config()
        self.showNormal()
        self.raise_()
        self.activateWindow()
