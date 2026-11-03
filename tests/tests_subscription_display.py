import base64
import json
from pathlib import Path
from quotaboard.subscription import read_codex_subscription_expiry, subscription_date
from quotaboard.model import QuotaResult
from quotaboard.taskbar import taskbar_label
from quotaboard.providers.codex_provider import CodexProvider

root=Path('dist/subscription-test');root.mkdir(parents=True,exist_ok=True)
path=root/'dummy-auth.json'
def write_claims(claims):
    payload=base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    path.write_text(json.dumps({'tokens':{'id_token':'test.'+payload+'.test'}}),encoding='utf8')
write_claims({'exp':1900000000,'https://api.openai.com/auth':{
    'chatgpt_subscription_active_until':'2026-12-01T12:00:00Z'}})
assert read_codex_subscription_expiry(path)==subscription_date('2026-12-01T12:00:00Z')
write_claims({'exp':1900000000})
assert not read_codex_subscription_expiry(path), 'token lifetime is not subscription validity'
write_claims({'https://api.openai.com/auth':{'chatgpt_subscription_active_until':None}})
assert not read_codex_subscription_expiry(path)
path.write_text('malformed',encoding='utf8');assert not read_codex_subscription_expiry(path)
assert not subscription_date(0) and not subscription_date('not a date')
response={'result':{'rateLimits':{'planType':'plus','primary':{
    'usedPercent':20,'resetsAt':1794000000,'windowDurationMins':300}}}}
result=CodexProvider({})._parse(response)
assert result.subscription_plan=='Plus' and taskbar_label(result)=='ChatGPT · Plus'
assert result.metrics[0]['resets_at']==1794000000
assert not result.subscription_expires_at, 'rate-limit resets are not membership expiry'
for key,plan,title in [('gemini','Pro','Gemini'),('doubao','标准套餐','豆包')]:
    row=QuotaResult(key,title,'80%',subscription_plan=plan)
    assert taskbar_label(row)==title+' · '+plan
assert taskbar_label(QuotaResult('deepseek','DeepSeek','¥18'))=='DeepSeek开放平台'
print('Subscription claims, malformed fallback, token/window expiry separation and taskbar plan labels passed')
