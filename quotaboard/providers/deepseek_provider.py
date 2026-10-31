"""DeepSeek 开放平台余额查询：GET api.deepseek.com/user/balance

返回：
    {"is_available": true,
     "balance_infos": [{"currency": "CNY",
                        "total_balance": "100.00",
                        "granted_balance": "0.00",
                        "topped_up_balance": "100.00"}]}

展示口径：直接显示账户余额数字（如 ¥100.00），余额无法换算百分比，
percent=None（不画条带）。
"""
from __future__ import annotations

import urllib.error

from ..model import QuotaResult
from .base import Provider, http_get_json

BALANCE_URL = "https://api.deepseek.com/user/balance"

# 币种 → 符号（用于余额展示）
_CURRENCY_SYMBOL = {
    "CNY": "¥",
    "USD": "$",
    "EUR": "€",
    "HKD": "HK$",
    "JPY": "¥",
    "GBP": "£",
}


class DeepSeekProvider(Provider):
    key = "deepseek"
    label = "DeepSeek"

    def fetch(self) -> QuotaResult:
        api_key = str(self.cfg.get("api_key", "")).strip()
        if not api_key:
            return self.err("未配置 API Key")

        try:
            data = http_get_json(BALANCE_URL, {
                "Authorization": f"Bearer {api_key}",
            }, timeout=20)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return self.err("API Key 无效或未授权（HTTP 401/403）")
            body = ""
            try:
                body = e.read(300).decode("utf-8", "replace")
            except Exception:
                pass
            return self.err(f"请求失败：HTTP {e.code} {body[:120]}")
        except Exception as e:
            return self.err(f"请求失败：{e}")

        infos = data.get("balance_infos") if isinstance(data, dict) else None
        if not isinstance(infos, list) or not infos:
            return self.err(f"响应缺少余额字段：{str(data)[:120]}")

        # 每个币种一行余额，多个币种用「 · 」连接
        parts = []
        for info in infos:
            total = info.get("total_balance")
            if total is None:
                continue
            currency = str(info.get("currency") or "USD").upper()
            symbol = _CURRENCY_SYMBOL.get(currency, f"{currency} ")
            try:
                parts.append(f"{symbol}{float(total):,.2f}")
            except (TypeError, ValueError):
                parts.append(f"{symbol}{total}")
        if not parts:
            return self.err("响应余额字段均为空")

        return QuotaResult(
            platform=self.key, label=self.label,
            display=" · ".join(parts),
            available=None, used=None, total=None,
            unit="", percent=None, ok=True,
        )
