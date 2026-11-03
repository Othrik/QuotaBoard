from pathlib import Path
import os,subprocess,json,time
from quotaboard.taskbar_snapshot import export_snapshot
from quotaboard.model import QuotaResult
base=Path('dist/widget-test').resolve();base.mkdir(parents=True,exist_ok=True)
class C: path=base/'QuotaBoard/config.json'
export_snapshot(C(),[QuotaResult(platform='deepseek',label='DeepSeek',display='¥12.34')])
assert 'credential' not in (base/'QuotaBoard/taskbar-snapshot.json').read_text('utf-8')
env={**os.environ,'APPDATA':str(base)}
p=subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path('com.othrik.quotaboard/provider.ps1').resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=env)
p.stdin.write(json.dumps({'type':'initialize','instances':[{'instanceId':'test','settings':{}}]})+'\n');p.stdin.flush()
line=p.stdout.readline();assert line,line
m=json.loads(line);assert m['instanceId']=='test' and m['data']['quota']=='¥12.34',m
p.stdin.write('{"type":"shutdown"}\n');p.stdin.flush();p.wait(timeout=10)
print('Credential-free snapshot and provider protocol passed')
