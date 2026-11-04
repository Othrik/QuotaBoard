"""Only changes since an AI's last aired quota trigger a finite animation."""
from dataclasses import replace
from tests.tests_rotation_interval import controller,config
from quotaboard.model import QuotaResult

a=QuotaResult('codex','ChatGPT','80%',metrics=[dict(label='5h',percent=80,note='18:00')])
b=QuotaResult('gemini','Gemini','90%',percent=90)
assert controller.presentation_change(a)=='0'
assert controller.presentation_change(b)=='0'
assert controller.presentation_change(replace(a,updated_at='later'))=='0'
changed=replace(a,metrics=[dict(label='5h',percent=79,note='18:00')])
# Merely fetching another AI must not overwrite this AI's baseline.
assert controller.presentation_change(b)=='0'
assert controller.presentation_change(changed)=='1'
assert controller.presentation_change(changed)=='1'
assert controller.presentation_change(replace(a,ok=False))=='1'
assert controller.presentation_change(changed)=='1'
assert controller.presentation_change(replace(b,percent=91))=='2'
assert controller.presentation_change(replace(changed,metrics=[dict(label='5h',percent=79,note='19:00')]))=='3'
controller.rotation_row([a],1000)
assert controller._rotation_deadline==float('inf')
assert controller.rotation_row([a],100000).platform=='codex'
assert controller.rotation_row([a,b],100001).platform=='codex'
assert controller.rotation_row([a,b],100013).platform=='gemini'
print('Per-AI aired baseline, timestamp exclusion, recovery, reset changes and single/multi transition passed')
