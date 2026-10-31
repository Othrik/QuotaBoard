"""Provider 抽象基类与通用 HTTP 工具。"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from ..model import QuotaResult

DEFAULT_HEADERS = {
    "User-Agent": "QuotaBoard/1.0 (Windows; +local desktop widget)",
    "Accept": "application/json",
}


def http_get_json(url: str, headers: dict[str, str] | None = None,
                  timeout: float = 15.0) -> dict:
    """GET 请求并解析 JSON；失败抛异常。"""
    req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout,
                                context=ssl.create_default_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url: str, body: dict, headers: dict[str, str] | None = None,
                   timeout: float = 15.0) -> dict:
    """POST JSON 请求并解析响应。"""
    data = json.dumps(body).encode("utf-8")
    hdrs = {**DEFAULT_HEADERS, "Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout,
                                context=ssl.create_default_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


class Provider(ABC):
    """平台适配器基类。子类实现 fetch() 返回标准 QuotaResult。"""

    key: str = ""
    label: str = ""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg

    @abstractmethod
    def fetch(self) -> QuotaResult:
        ...

    def err(self, message: str) -> QuotaResult:
        return QuotaResult(platform=self.key, label=self.label,
                           display="—", ok=False, error=message)
