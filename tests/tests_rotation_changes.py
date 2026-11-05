"""Rotation selects models; native animation keys only on platform changes."""
from tests.tests_rotation_interval import controller,config
from quotaboard.model import QuotaResult

a=QuotaResult('codex','ChatGPT','80%',metrics=[dict(label='5h',percent=80,note='18:00')])
b=QuotaResult('gemini','Gemini','90%',percent=90)
assert not hasattr(controller,'presentation_change')
controller.rotation_row([a],1000)
assert controller._rotation_deadline==float('inf')
assert controller.rotation_row([a],100000).platform=='codex'
assert controller.rotation_row([a,b],100001).platform=='codex'
assert controller.rotation_row([a,b],100013).platform=='gemini'
print('Single-AI stability and multi-model rotation transition points passed')
