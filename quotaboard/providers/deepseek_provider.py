"""DeepSeek public API balance and paid/granted breakdown (no web session)."""
from __future__ import annotations
from decimal import Decimal,InvalidOperation
import math
import urllib.error
from ..model import QuotaResult
from .base import Provider,http_get_json

BALANCE_URL='https://api.deepseek.com/user/balance'
_CURRENCY_SYMBOL={'CNY':'¥','USD':'$','EUR':'€','HKD':'HK$','JPY':'¥','GBP':'£'}


def _amount(value):
    if value is None or isinstance(value,bool):return None
    try:
        number=Decimal(str(value))
        return number if number.is_finite() and math.isfinite(float(number)) else None
    except (ValueError,InvalidOperation,OverflowError):return None


def _money(value,currency):
    symbol=_CURRENCY_SYMBOL.get(currency,currency+' ')
    whole,_,fraction=format(abs(value),',.4f').partition('.')
    return ('-' if value<0 else '')+symbol+whole+'.'+fraction.rstrip('0').ljust(2,'0')


class DeepSeekProvider(Provider):
    key='deepseek'
    label='DeepSeek开放平台'

    def fetch(self):
        api_key=str(self.cfg.get('api_key','')).strip()
        if not api_key:return self.err('未配置 API Key')
        try:
            data=http_get_json(BALANCE_URL,{'Authorization':'Bearer '+api_key},timeout=20)
        except urllib.error.HTTPError as error:
            if error.code in (401,403):return self.err('API Key 无效或未授权（HTTP 401/403）')
            if error.code==429:return self.err('查询过于频繁，稍后自动重试')
            return self.err(f'余额查询失败（HTTP {error.code}）')
        except Exception:
            return self.err('余额查询连接失败，稍后自动重试')
        return self._parse(data)

    def _parse(self,data):
        infos=data.get('balance_infos') if isinstance(data,dict) else None
        if not isinstance(infos,list) or not infos:return self.err('响应缺少余额字段')
        balances=[];details=[]
        for info in infos:
            if not isinstance(info,dict):continue
            total=_amount(info.get('total_balance'))
            currency=str(info.get('currency') or '').strip().upper()
            if total is None or not currency or len(currency)>8 or not currency.isalpha():
                continue
            balances.append((currency,total))
            for key,caption in [('topped_up_balance','充值余额'),('granted_balance','赠送余额')]:
                value=_amount(info.get(key))
                if value is not None:
                    details.append(dict(label=caption+' · '+currency,value=_money(value,currency)))
        if not balances:return self.err('响应未提供有效币种及余额')
        available=data.get('is_available') if isinstance(data.get('is_available'),bool) else None
        if available is not None:
            details.append(dict(label='API 余额状态',value='余额充足，可调用' if available else '余额不足以调用'))
        return QuotaResult(platform=self.key,label=self.label,
            display=' · '.join(_money(value,currency) for currency,value in balances),
            available=float(balances[0][1]) if len(balances)==1 else None,
            unit=balances[0][0] if len(balances)==1 else '',
            percent=None,used=None,total=None,ok=True,
            details=details,account_available=available)
