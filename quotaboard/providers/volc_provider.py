"""火山方舟（豆包 API）用量查询：火山引擎 OpenAPI + AK/SK HMAC-SHA256 签名。

支持两个 Action：
- GetUsageDetails       查询个人版 AgentPlan 套餐模型调用用量
- ListModelInferenceLimits  查询模型推理用量限额与累计用量

签名流程对齐火山引擎官方签名算法（HMAC-SHA256 / ark / cn-beijing）。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timezone

from ..model import QuotaResult
from .base import Provider

SERVICE = "ark"
REGION = "cn-beijing"
HOST = "ark.cn-beijing.volcengineapi.com"
BASE_URL = f"https://{HOST}/"


def _encode(s: str) -> str:
    """RFC3986 unreserved 字符集外的字符百分号编码。"""
    return urllib.parse.quote(s, safe="-_.~")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _build_signature(ak: str, sk: str, query_params: dict[str, str],
                     body: dict) -> dict[str, str]:
    """按火山引擎签名算法生成请求头。"""
    now = datetime.now(timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = x_date[:8]

    body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_hash = _sha256_hex(body_bytes)

    # CanonicalQueryString：参数按 key 排序
    cqs = "&".join(f"{_encode(k)}={_encode(v)}"
                   for k, v in sorted(query_params.items()))

    content_type = "application/json"
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{HOST}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{x_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"

    canonical_request = "\n".join([
        "POST", "/", cqs, canonical_headers, signed_headers, payload_hash,
    ])

    credential_scope = f"{date}/{REGION}/{SERVICE}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256", x_date, credential_scope, _sha256_hex(canonical_request.encode("utf-8")),
    ])

    k_date = _hmac_sha256(sk.encode("utf-8"), date)
    k_region = _hmac_sha256(k_date, REGION)
    k_service = _hmac_sha256(k_region, SERVICE)
    k_signing = _hmac_sha256(k_service, "request")
    signature = _hmac_sha256(k_signing, string_to_sign).hex()

    authorization = (
        f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Host": HOST,
        "X-Date": x_date,
        "X-Content-Sha256": payload_hash,
        "Content-Type": content_type,
        "Authorization": authorization,
    }


def _find_numeric(data, keys: tuple[str, ...]) -> float | None:
    """在嵌套 dict/list 中按候选 key 找第一个数值。"""
    if isinstance(data, dict):
        for k, v in data.items():
            low = str(k).lower()
            if any(key in low for key in keys):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
            hit = _find_numeric(v, keys)
            if hit is not None:
                return hit
    elif isinstance(data, list):
        for item in data:
            hit = _find_numeric(item, keys)
            if hit is not None:
                return hit
    return None


class VolcProvider(Provider):
    key = "volc"
    label = "火山方舟"

    def fetch(self) -> QuotaResult:
        ak = str(self.cfg.get("ak", "")).strip()
        sk = str(self.cfg.get("sk", "")).strip()
        if not ak or not sk:
            return self.err("未配置 Access Key / Secret Key")

        action = str(self.cfg.get("action", "GetUsageDetails")).strip() or "GetUsageDetails"
        query = {"Action": action, "Version": "2024-01-01"}
        body: dict = {}

        try:
            headers = _build_signature(ak, sk, query, body)
        except Exception as e:
            return self.err(f"签名失败：{e}")

        from .base import http_post_json
        url = BASE_URL + "?" + urllib.parse.urlencode(query)
        try:
            resp = http_post_json(url, body, headers=headers, timeout=20)
        except Exception as e:
            return self.err(f"请求失败：{e}")

        # 错误处理
        meta = resp.get("ResponseMetadata") if isinstance(resp, dict) else None
        if isinstance(meta, dict) and isinstance(meta.get("Error"), dict):
            err = meta["Error"]
            return self.err(f"接口报错 {err.get('Code', '?')}：{err.get('Message', '')}")

        usage = _find_numeric(resp, ("usage", "tokens", "limit", "inference"))
        if usage is None:
            return self.err(f"响应中未找到用量字段：{str(resp)[:160]}")

        # 若同时拿到限额与累计用量，给出剩余占比
        limit = _find_numeric(resp, ("limit", "quota", "total"))
        if action == "ListModelInferenceLimits" and limit and limit > 0:
            percent = max(0.0, min(100.0, usage / limit * 100))
            display = f"{usage:,.0f}"
            return QuotaResult(
                platform=self.key, label=self.label, display=display,
                available=limit - usage, used=usage, total=limit,
                unit="tokens", percent=percent, ok=True,
            )

        return QuotaResult(
            platform=self.key, label=self.label, display=f"{usage:,.0f}",
            available=usage, used=None, total=None,
            unit="tokens", percent=None, ok=True,
        )
