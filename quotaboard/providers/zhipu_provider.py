"""智谱 GLM 额度查询：GET open.bigmodel.cn/api/paas/v4/balance

返回资源包/现金账户余额列表，每项含 resource_id / available / total / used。
"""
from __future__ import annotations

from ..model import QuotaResult
from .base import Provider, http_get_json

BALANCE_URL = "https://open.bigmodel.cn/api/paas/v4/balance"


class ZhipuProvider(Provider):
    key = "zhipu"
    label = "智谱 GLM"

    def fetch(self) -> QuotaResult:
        api_key = str(self.cfg.get("api_key", "")).strip()
        if not api_key:
            return self.err("未配置 API Key")
        try:
            data = http_get_json(BALANCE_URL, {"Authorization": f"Bearer {api_key}"})
        except Exception as e:
            return self.err(f"请求失败：{e}")

        items = data.get("list") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            return self.err(f"响应缺少余额列表：{str(data)[:120]}")

        available = sum(float(i.get("available") or 0) for i in items)
        total = sum(float(i.get("total") or 0) for i in items)
        used = sum(float(i.get("used") or 0) for i in items)
        percent = (available / total * 100) if total > 0 else None

        # 展示取现金账户（resource_id == cash）优先，否则用合计
        cash = next((i for i in items if str(i.get("resource_id", "")).lower() == "cash"), None)
        display_available = float(cash.get("available") or 0) if cash else available
        display = f"¥{display_available:,.2f}"

        return QuotaResult(
            platform=self.key, label=self.label,
            display=display,
            available=available, used=used, total=total, unit="CNY",
            percent=percent, ok=True,
        )
