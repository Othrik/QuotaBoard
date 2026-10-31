"""统一数据模型：每个平台的额度查询结果与平台元信息。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class QuotaResult:
    """一个平台单次额度查询的结果，UI 层只消费该模型。"""

    platform: str            # 平台 key，如 openai / zhipu / kimi / volc / manual
    label: str               # 展示名，如 "OpenAI" / "智谱 GLM"
    display: str             # 剩余额度的展示文本，如 "$12.35" / "¥86.40" / "3764k"
    available: Optional[float] = None   # 剩余数值
    total: Optional[float] = None       # 总量数值
    used: Optional[float] = None        # 已用数值
    unit: str = ""           # 单位：USD / CNY / tokens / 次
    percent: Optional[float] = None     # 剩余百分比 0-100，None 表示不可计算
    ok: bool = True          # 是否查询成功
    error: str = ""          # 失败原因（ok=False 时）
    sub_note: str = ""       # 副行补充信息（如重置时间、多窗口详情）
    updated_at: str = ""     # 更新时间（ISO 字符串）
    metrics: Optional[list] = None  # 多窗口环形图数据：[{"label","percent","note"}...]

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def status_level(self) -> str:
        """状态等级：ok(正常) / warn(偏低) / danger(告警或失败)。
        颜色规则：剩余 ≥75% 绿色，<30% 红色，中间黄色。"""
        if not self.ok:
            return "danger"
        if self.percent is None:
            return "ok"
        if self.percent < 30:
            return "danger"
        if self.percent < 75:
            return "warn"
        return "ok"


# 平台注册元信息（展示顺序、设置项名称等）
PLATFORM_META: dict[str, dict] = {
    "openai": {"label": "OpenAI", "credential_fields": [("api_key", "API Key")]},
    "chatgpt_plus": {
        "label": "ChatGPT Plus",
        "credential_fields": [("session_token", "登录 Token")],
    },
    "codex": {
        "label": "ChatGPT",
        "credential_fields": [],
    },
    "doubao": {
        "label": "豆包",
        "credential_fields": [("manual_sessionid", "手动 sessionid（可选）")],
    },
    "zhipu": {"label": "智谱 GLM", "credential_fields": [("api_key", "API Key")]},
    "zhipu_member": {
        "label": "智谱清言",
        "credential_fields": [("manual_token", "手动 Token（可选）")],
    },
    "kimi": {"label": "Kimi", "credential_fields": [("api_key", "API Key")]},
    "deepseek": {
        "label": "DeepSeek",
        "credential_fields": [("api_key", "API Key")],
    },
    "volc": {
        "label": "火山方舟",
        "credential_fields": [("ak", "Access Key"), ("sk", "Secret Key")],
    },
    "manual": {"label": "手动额度", "credential_fields": []},
}
