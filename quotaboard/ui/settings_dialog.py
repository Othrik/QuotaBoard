"""设置对话框：平台凭据配置、刷新间隔、手动额度维护。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QListWidget, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from ..config import Config
from ..model import PLATFORM_META
from ..providers import PROVIDERS

FIELDS_LABEL = {"api_key": "API Key", "ak": "Access Key", "sk": "Secret Key",
                "manual_token": "手动 Token"}


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("QuotaBoard 设置")
        self.setMinimumWidth(720)
        self.setStyleSheet("""
            QDialog { background: #F5F7FB; color: #202938; font-family: Segoe UI; font-size: 13px; }
            QGroupBox { background: white; border: 1px solid #E2E7F0; border-radius: 12px; margin-top: 14px; padding: 20px 16px 16px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 6px; }
            QLineEdit, QSpinBox, QComboBox { background: white; border: 1px solid #DCE2EC; border-radius: 7px; padding: 8px; min-height: 18px; }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #527BEE; }
            QPushButton { background: white; border: 1px solid #DCE2EC; border-radius: 7px; padding: 8px 16px; color: #344054; }
            QPushButton:hover { background: #EDF2FF; border-color: #A8BAEF; }
            QPushButton#primary { background: #4169E1; color: white; border: none; }
            QListWidget { background: #EBEFF7; border: none; border-radius: 10px; padding: 6px; outline: none; }
            QListWidget::item { padding: 12px 10px; border-radius: 6px; margin: 2px 0; }
            QListWidget::item:selected { background: white; color: #365CC5; }
            QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
            QTableWidget { background: white; border: 1px solid #DCE2EC; gridline-color: #EDF0F5; }
            QHeaderView::section { background: #EDF2FA; border: none; padding: 8px; }
        """)
        self._build_ui()
        self._load()
        # 初始尺寸适配屏幕：高不超过可用高度，内容超高时由滚动区承接
        geo = QApplication.primaryScreen().availableGeometry()
        self.resize(min(860, geo.width() - 60),
                    min(int(geo.height() * 0.88), geo.height() - 60))

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 12, 12, 10)

        heading = QLabel("偏好设置")
        heading.setStyleSheet("font-size: 22px; font-weight: 600; padding: 6px;")
        lay.addWidget(heading)
        content = QHBoxLayout()
        self.navigation = QListWidget()
        self.navigation.setFixedWidth(170)
        content.addWidget(self.navigation)

        # ---- 可滚动内容区（平台配置 + 间隔 + 手动额度） ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        clay = QVBoxLayout(container)
        clay.setSpacing(12)
        clay.setContentsMargins(2, 2, 2, 2)

        title = QLabel("连接你的 AI 平台 · 凭据仅保存在本机并加密")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        clay.addWidget(title)

        self.platform_boxes: dict[str, QGroupBox] = {}
        self.field_inputs: dict[str, dict[str, QLineEdit]] = {}
        self.enable_checks: dict[str, QCheckBox] = {}
        self.volc_actions: dict[str, QComboBox] = {}

        for key, meta in PLATFORM_META.items():
            box = QGroupBox(meta["label"])
            v = QVBoxLayout(box)
            v.setSpacing(6)

            chk = QCheckBox("启用此平台")
            v.addWidget(chk)
            self.enable_checks[key] = chk

            if key == "chatgpt_plus":
                guide = QLabel(
                    "登录 Token 提取：浏览器登录 chatgpt.com → F12 开发者工具 → "
                    "Application → Cookies → 复制 __Secure-next-auth.session-token "
                    "的值。Token 过期后需重新提取。")
                guide.setWordWrap(True)
                guide.setStyleSheet(
                    "font-size: 11px; color: #646A73; background: #F5F7FA;"
                    " border-radius: 6px; padding: 6px 8px;")
                v.addWidget(guide)

            if key == "gemini":
                guide = QLabel("自动读取 Gemini 客户端登录态查询会员额度。首次读取被锁文件可能需要管理员授权，成功后加密缓存在本机。无需停留在用量页。")
                guide.setWordWrap(True)
                v.addWidget(guide)

            if key == "codex":
                guide = QLabel(
                    "无需填写凭据：通过官方本地协议读取你 ChatGPT 账号的"
                    "5 小时与每周用量限额（使用 ChatGPT Windows 应用内置的"
                    "Codex，或 npm 安装的 Codex CLI），鉴权由已登录的账号"
                    "处理。未找到 codex 时请安装 ChatGPT Windows 应用或"
                    "Codex CLI。")
                guide.setWordWrap(True)
                guide.setStyleSheet(
                    "font-size: 11px; color: #646A73; background: #F5F7FA;"
                    " border-radius: 6px; padding: 6px 8px;")
                v.addWidget(guide)

            if key == "zhipu_member":
                guide = QLabel(
                    "自动读取智谱清言客户端登录态（%APPDATA%\\chatglm\\Network"
                    "\\Cookies）并加密缓存；客户端运行期间也可正常显示。"
                    "首次使用请在客户端关闭状态下刷新一次，或在此手动粘贴"
                    "chatglm_token。登录态过期时打开客户端重新登录即可续期。")
                guide.setWordWrap(True)
                guide.setStyleSheet(
                    "font-size: 11px; color: #646A73; background: #F5F7FA;"
                    " border-radius: 6px; padding: 6px 8px;")
                v.addWidget(guide)

            if key == "doubao":
                guide = QLabel(
                    "自动检测豆包客户端的登录会话并读取订阅额度（5 小时 / 周"
                    "双窗口 + 活动赠送），读取成功后加密缓存，客户端关闭也能"
                    "显示。首次使用请先打开豆包客户端并登录；接口失效时可在"
                    "下方手动粘贴 sessionid。")
                guide.setWordWrap(True)
                guide.setStyleSheet(
                    "font-size: 11px; color: #646A73; background: #F5F7FA;"
                    " border-radius: 6px; padding: 6px 8px;")
                v.addWidget(guide)

            inputs: dict[str, QLineEdit] = {}
            for field, _label in meta["credential_fields"]:
                row = QHBoxLayout()
                lab = QLabel(FIELDS_LABEL.get(field, field))
                lab.setFixedWidth(90)
                ed = QLineEdit()
                ed.setEchoMode(QLineEdit.EchoMode.Password)
                ed.setPlaceholderText("已保存则留空，仅修改时填写")
                row.addWidget(lab)
                row.addWidget(ed, 1)
                v.addLayout(row)
                inputs[field] = ed
            self.field_inputs[key] = inputs

            if key == "volc":
                arow = QHBoxLayout()
                alab = QLabel("查询方式")
                alab.setFixedWidth(90)
                combo = QComboBox()
                combo.addItems(["GetUsageDetails（套餐用量）",
                                "ListModelInferenceLimits（模型推理限额）"])
                arow.addWidget(alab)
                arow.addWidget(combo, 1)
                v.addLayout(arow)
                self.volc_actions[key] = combo

            tbtn = QPushButton("测试连接")
            tbtn.clicked.connect(lambda _=False, k=key: self._test(k))
            v.addWidget(tbtn)
            clay.addWidget(box)
            self.navigation.addItem(meta["label"])
            self.platform_boxes[key] = box

        general = QWidget()
        general_layout = QVBoxLayout(general)
        self.navigation.addItem("通用设置")

        # ---- 刷新间隔 ----
        form = QFormLayout()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setSuffix(" 分钟")
        form.addRow("自动刷新间隔", self.interval_spin)
        general_layout.addLayout(form)

        general_layout.addStretch(1)
        clay.addWidget(general)
        clay.addStretch(1)
        pages = list(self.platform_boxes.values()) + [general]
        def select_page(index):
            for i, page in enumerate(pages):
                page.setVisible(i == index)
            scroll.verticalScrollBar().setValue(0)
        self.navigation.currentRowChanged.connect(select_page)
        self.navigation.setCurrentRow(0)
        scroll.setWidget(container)
        content.addWidget(scroll, 1)
        lay.addLayout(content, 1)

        # ---- 保存（固定在窗口底部） ----
        btns = QHBoxLayout()
        btns.addStretch(1)
        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("primary")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        lay.addLayout(btns)

    # ---------- 载入 ----------
    def _load(self) -> None:
        for key, meta in PLATFORM_META.items():
            self.enable_checks[key].setChecked(self.config.is_enabled(key))
            for field, _ in meta["credential_fields"]:
                saved = self.config.get_credential(key, field)
                self.field_inputs[key][field].setText(saved)
                self.field_inputs[key][field].setPlaceholderText(
                    "已保存（留空则不修改）" if saved else "未配置")
            if key == "volc":
                action = self.config.platform_cfg(key).get("action", "GetUsageDetails")
                self.volc_actions[key].setCurrentIndex(
                    1 if action == "ListModelInferenceLimits" else 0)

        self.interval_spin.setValue(self.config.refresh_interval_minutes)

    # ---------- 测试 ----------
    def _test(self, key: str) -> None:
        cfg = {f: ed.text().strip() or self.config.get_credential(key, f)
               for f, ed in self.field_inputs[key].items()}
        if key == "volc":
            cfg["action"] = ("ListModelInferenceLimits"
                             if self.volc_actions[key].currentIndex() == 1
                             else "GetUsageDetails")
        try:
            provider = PROVIDERS[key](cfg)
            from ..model import QuotaResult
            result: QuotaResult = provider.fetch()
        except Exception as e:
            QMessageBox.warning(self, "测试失败", f"{key} 测试异常：{e}")
            return
        if result.ok:
            QMessageBox.information(self, "连接成功",
                                    f"{result.label} 当前剩余：{result.display}")
        else:
            QMessageBox.warning(self, "连接失败", f"{result.label}：{result.error}")

    # ---------- 保存 ----------
    def _save(self) -> None:
        for key, meta in PLATFORM_META.items():
            self.config.set_enabled(key, self.enable_checks[key].isChecked())
            for field, _ in meta["credential_fields"]:
                text = self.field_inputs[key][field].text().strip()
                if text:
                    self.config.set_credential(key, field, text)
            if key == "volc":
                self.config.platform_cfg(key)["action"] = (
                    "ListModelInferenceLimits"
                    if self.volc_actions[key].currentIndex() == 1
                    else "GetUsageDetails")

        self.config.refresh_interval_minutes = self.interval_spin.value()

        try:
            self.config.save()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self.accept()
