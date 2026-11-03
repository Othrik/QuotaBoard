"""Prepaid CNY account balance from BigModel's console account-report route.

The endpoint accepts a regular API key; it is separate from Coding Plan quota.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import math
import urllib.error
from ..model import QuotaResult
from .base import Provider, http_get_json

BALANCE_URL = 'https://open.bigmodel.cn/api/biz/account/query-customer-account-report'
BALANCE_FALLBACK_URL = 'https://www.bigmodel.cn/api/biz/account/query-customer-account-report'


def amount(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and math.isfinite(float(number)) else None
    except (ValueError, InvalidOperation, OverflowError):
        return None


def money(value):
    return '¥' + format(value, ',.4f')


class ZhipuProvider(Provider):
    key = 'zhipu'
    label = '智谱 GLM'

    def fetch(self) -> QuotaResult:
        api_key = str(self.cfg.get('api_key', '')).strip()
        if not api_key:
            return self.err('未配置 API Key')
        headers = {'Authorization': 'Bearer ' + api_key}
        error_message = '暂时无法查询余额'
        for url in (BALANCE_URL, BALANCE_FALLBACK_URL):
            try:
                data = http_get_json(url, headers)
            except urllib.error.HTTPError as error:
                if error.code == 401:
                    return self.err('API Key 鉴权失败，请检查智谱开放平台密钥')
                if error.code == 429:
                    return self.err('余额查询过于频繁，稍后自动重试')
                error_message = f'余额查询暂不可用（HTTP {error.code}）'
                if error.code in (403, 404, 500, 502, 503, 504):
                    continue
                return self.err(error_message)
            except Exception:
                error_message = '余额查询连接失败，稍后自动重试'
                continue
            if not isinstance(data, dict) or data.get('success') is not True or str(data.get('code')) != '200':
                # Do not expose a raw response (which may include account data).
                code = str(data.get('code', '未知'))[:16] if isinstance(data, dict) else '格式异常'
                if not code.isalnum():
                    code = '未知'
                return self.err(f'余额接口未通过校验（{code}），请检查密钥或稍后重试')
            return self._parse_report(data)
        return self.err(error_message)

    def _parse_report(self, data):
        report = data.get('data')
        if not isinstance(report, dict):
            return self.err('响应缺少账户余额数据')
        available = amount(report.get('availableBalance'))
        if available is None:
            available = amount(report.get('balance'))
        if available is None:
            return self.err('响应未提供有效余额，稍后自动重试')
        notes = []
        for key, caption in [('rechargeAmount', '累计充值'), ('totalSpendAmount', '累计消费'), ('frozenBalance', '冻结')]:
            value = amount(report.get(key))
            if value is not None:
                notes.append(caption + ' ' + money(value))
        # Lifetime recharge/spend is not a replenishing quota; no percentage ring.
        spent = amount(report.get('totalSpendAmount'))
        return QuotaResult(platform=self.key, label=self.label, display=money(available),
                           available=float(available), used=float(spent) if spent is not None else None,
                           unit='CNY', percent=None, total=None, ok=True, sub_note=' · '.join(notes))
