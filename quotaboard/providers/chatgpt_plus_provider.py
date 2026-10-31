"""ChatGPT Plus 订阅额度查询（登录态模式，试点）。

原理：借用用户已登录 chatgpt.com 的会话 token（__Secure-next-auth.session-token），
调用网页端未公开接口。非官方手段，接口可能随平台调整而失效。

实现策略：
1. accounts/check 接口获取套餐状态（可靠，社区长期验证）；
2. 用量端点（剩余消息额度等）没有公开稳定的社区文档，代码做宽容探测，
   实测后按真实响应精修字段解析。
"""
from __future__ import annotations

from ..model import QuotaResult
from .base import Provider, http_get_json

BASE = "https://chatgpt.com"
ACCOUNT_CHECK = BASE + "/backend-api/accounts/check/v4-2023-04-27"
# 候选用量端点（按社区出现频率排序；404 时静默跳过）
USAGE_CANDIDATES = [
    BASE + "/backend-api/usage",
]

PLAN_NAMES = {
    "free": "Free", "plus": "Plus", "pro": "Pro", "business": "Business",
    "team": "Team", "enterprise": "Enterprise", "edu": "Edu",
}


def _cookies(token: str) -> dict:
    return {"Cookie": f"__Secure-next-auth.session-token={token}"}


def _find_number(data, keys: tuple[str, ...]):
    """宽容递归查找数值字段。"""
    if isinstance(data, dict):
        for k, v in data.items():
            low = str(k).lower()
            if any(key in low for key in keys):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
            hit = _find_number(v, keys)
            if hit is not None:
                return hit
    elif isinstance(data, list):
        for item in data:
            hit = _find_number(item, keys)
            if hit is not None:
                return hit
    return None


class ChatGPTPlusProvider(Provider):
    key = "chatgpt_plus"
    label = "ChatGPT Plus"

    def fetch(self) -> QuotaResult:
        token = str(self.cfg.get("session_token", "")).strip()
        if not token:
            return self.err("未配置登录 Token（浏览器 Cookie 提取）")

        try:
            data = http_get_json(ACCOUNT_CHECK, _cookies(token), timeout=20)
        except Exception as e:
            return self.err(f"请求失败：{e}（Token 可能已过期）")

        if isinstance(data, dict) and data.get("detail") == "Unauthorized":
            return self.err("Token 无效或已过期，请重新提取")

        plan = str(data.get("plan_type", "") or "unknown")
        plan_label = PLAN_NAMES.get(plan, plan.capitalize())

        # 用量探测：先在 accounts 响应里找，找不到再试候选端点
        used = _find_number(data, ("usage", "messages_used", "used"))
        limit = _find_number(data, ("limit", "messages_limit", "quota", "total"))

        if used is None:
            for url in USAGE_CANDIDATES:
                try:
                    u = http_get_json(url, _cookies(token), timeout=10)
                except Exception:
                    continue
                used = _find_number(u, ("usage", "used", "messages_used", "remaining"))
                limit = _find_number(u, ("limit", "total", "messages_limit"))
                if used is not None or limit is not None:
                    break

        if limit and limit > 0 and used is not None:
            remaining = max(0.0, limit - used)
            percent = remaining / limit * 100
            return QuotaResult(
                platform=self.key, label=self.label,
                display=f"{remaining:,.0f}",
                available=remaining, used=used, total=limit,
                unit="次", percent=percent, ok=True,
            )

        # 拿到套餐但未解析到用量：连接成功，提示待校准
        note = f"{plan_label} 已订阅"
        return QuotaResult(
            platform=self.key, label=self.label,
            display=note, available=None, used=None, total=None,
            unit="", percent=None, ok=True,
            error="", updated_at="",
        ) if not self.cfg.get("strict") else self.err(
            f"已获取套餐（{plan_label}），但未解析到用量字段，请把调试信息发回校准")

    # 供测试与联调：返回完整原始响应片段
    def debug_fetch(self) -> tuple[bool, str, object]:
        token = str(self.cfg.get("session_token", "")).strip()
        if not token:
            return False, "未配置 Token", None
        try:
            data = http_get_json(ACCOUNT_CHECK, _cookies(token), timeout=20)
            return True, "ok", data
        except Exception as e:
            return False, str(e), None
