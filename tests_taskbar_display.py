from pathlib import Path
import subprocess,json
src=Path('com.othrik.quotaboard/provider.ps1').read_text(encoding='utf-8-sig')
base=Path('dist/widget-logic-tests');base.mkdir(exist_ok=True)
(base/'functions.ps1').write_text(src.split('$instances=@()')[0],encoding='utf-8-sig')
cases=[
 ({'ok':True,'metrics':[{'label':'5h','percent':94},{'label':'周','percent':29}]},'5h 94% · 周 29%','#FF27AE80','#FFE45D6A'),
 ({'ok':True,'metrics':[{'label':'5h','percent':30},{'label':'周','percent':75}]},'5h 30% · 周 75%','#FFE5A132','#FF27AE80'),
 ({'ok':True,'metrics':[{'label':'5h','percent':0,'note':'5h重置 03:05'},{'label':'周','percent':60}]},'5h 03:05重置 · 周 60%',None,'#FFE5A132'),
 ({'ok':True,'metrics':[{'label':'5h','percent':0},{'label':'周','percent':0,'note':'周重置 11-07 20:01'}]},'11月7日 20:01 周重置',None,None),
 ({'ok':True,'metrics':[{'label':'周','percent':0}]},'周额度用完，等待重置',None,None),
 ({'ok':True,'metrics':[],'display':'积分 23,854.36'},'积分 23,854.36',None,None),
 ({'ok':True,'metrics':[],'display':'剩余 28%','percent':28},'剩余 28%','#FFE45D6A',None),
 ({'ok':False,'metrics':[]},'请求失败',None,None),
]
(base/'cases.json').write_text(json.dumps([c[0] for c in cases],ensure_ascii=False),encoding='utf-8-sig')
(base/'test.ps1').write_text(". $PSScriptRoot/functions.ps1\n$cases=Get-Content $PSScriptRoot/cases.json -Raw -Encoding UTF8|ConvertFrom-Json\nforeach($item in $cases){$data=@{};Set-QuotaParts $data $item;$data|ConvertTo-Json -Compress}\n",encoding='utf-8-sig')
r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str((base/'test.ps1').resolve())],capture_output=True,text=True,encoding='utf8',check=True)
rows=[json.loads(line) for line in r.stdout.splitlines() if line.strip()]
assert len(rows)==len(cases),(r.stdout,r.stderr)
for d,(_,text,c0,c1) in zip(rows,cases):
 actual=''.join(d[k] for k in ['alert','head0','value0','separator','head1','value1','suffix'])
 assert actual==text,(actual,text)
 if c0:assert d['valueColor0']==c0,d
 if c1:assert d['valueColor1']==c1,d
 if '重置' in text:assert d['alert'] or d['valueColor0']=='#FFE45D6A',d
print('8 quota scenarios passed: independent colors, boundaries, reset priority, precision, balance, failure')
