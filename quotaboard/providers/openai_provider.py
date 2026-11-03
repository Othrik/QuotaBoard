"""OpenAI 额度查询：GET api.openai.com/dashboard/billing/credit_grants

返回 total_granted / total_used / total_available（美元）。
该端点为社区长期验证的非官方 billing 接口；失败时自动提示。
"""
from __future__ import annotations

from ..model import QuotaResult
from .base import Provider, http_get_json

CREDIT_URL = "https://api.openai.com/dashboard/billing/credit_grants"


class OpenAIProvider(Provider):
    key = "openai"
    label = "Open AI API Platform"

    def fetch(self) -> QuotaResult:
        api_key = str(self.cfg.get("api_key", "")).strip()
        if not api_key:
            return self.err("未配置 API Key")
        try:
            data = http_get_json(CREDIT_URL, {"Authorization": f"Bearer {api_key}"})
        except Exception as e:
            return self.err(f"请求失败：{e}")

        total_granted = data.get("total_granted")
        total_used = data.get("total_used")
        total_available = data.get("total_available")
        if total_available is None:
            return self.err(f"响应缺少额度字段：{str(data)[:120]}")

        total = float(total_granted or 0)
        used = float(total_used or 0)
        available = float(total_available)
        percent = (available / total * 100) if total > 0 else None

        return QuotaResult(
            platform=self.key, label=self.label,
            display=f"${available:,.4f}",
            available=available, used=used, total=total, unit="USD",
            percent=percent, ok=True,
        )
