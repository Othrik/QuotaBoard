"""Kimi（月之暗面）额度查询：GET api.moonshot.cn/v1/users/me/balance

返回 available_balance（可用，含现金与赠金）、voucher_balance、cash_balance。
"""
from __future__ import annotations

from ..model import QuotaResult
from .base import Provider, http_get_json

BALANCE_URL = "https://api.moonshot.cn/v1/users/me/balance"


class KimiProvider(Provider):
    key = "kimi"
    label = "Kimi"

    def fetch(self) -> QuotaResult:
        api_key = str(self.cfg.get("api_key", "")).strip()
        if not api_key:
            return self.err("未配置 API Key")
        try:
            data = http_get_json(BALANCE_URL, {"Authorization": f"Bearer {api_key}"})
        except Exception as e:
            return self.err(f"请求失败：{e}")

        available = data.get("available_balance")
        if available is None:
            return self.err(f"响应缺少余额字段：{str(data)[:120]}")

        available = float(available)
        cash = float(data.get("cash_balance") or 0)
        voucher = float(data.get("voucher_balance") or 0)
        used = max(0.0, cash + voucher - available)  # 无总量口径时不下结论

        return QuotaResult(
            platform=self.key, label=self.label,
            display=f"${available:,.4f}",
            available=available, used=used,
            total=None, unit="USD", percent=None, ok=True,
        )
