"""DMXAPI CN account balance. Docs: https://doc.dmxapi.cn/yuer.html"""
from decimal import Decimal, InvalidOperation
import urllib.error
from .base import Provider, http_get_json
from ..model import QuotaResult
BALANCE_URL = 'https://www.dmxapi.cn/api/user/self'

class DMXAPIProvider(Provider):
    key = 'dmxapi'
    label = 'DMXAPI'
    def fetch(self):
        token = str(self.cfg.get('system_token', '')).strip()
        user_id = str(self.cfg.get('user_id', '')).strip()
        if not token or not user_id:
            return self.err('请配置系统访问令牌和用户 ID（不是模型调用 API Key）')
        if not user_id.isascii() or not user_id.isdigit():
            return self.err('用户 ID 应为数字')
        try:
            data = http_get_json(BALANCE_URL, {'Authorization': f'Bearer {token}', 'Dmx-Api-User': user_id}, timeout=20)
        except urllib.error.HTTPError as e:
            return self.err('系统访问令牌或用户 ID 无效/未授权' if e.code in (401,403) else f'余额查询失败：HTTP {e.code}')
        except Exception:
            return self.err('无法连接 DMXAPI，请检查网络后重试')
        if not isinstance(data, dict) or data.get('success') is not True:
            return self.err('DMXAPI 未返回成功结果，请检查系统令牌与用户 ID')
        try:
            balance = Decimal(str(data['data']['quota'])) / Decimal(500000)
            if not balance.is_finite(): raise ValueError()
        except (KeyError,TypeError,ValueError,InvalidOperation):
            return self.err('响应缺少有效余额字段')
        return QuotaResult(platform=self.key,label=self.label,display=f'¥{balance:,.4f}',available=float(balance),unit='CNY',percent=None,ok=True)
