$ErrorActionPreference='Stop'
[Console]::InputEncoding=[Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
Add-Type @"
using System; using System.Collections.Concurrent; using System.Threading;
public static class QuotaInput {
 public static ConcurrentQueue<string> Lines = new ConcurrentQueue<string>();
 public static volatile bool Ended;
 public static void Start() { var t = new Thread(() => { string l; while((l=Console.ReadLine())!=null) Lines.Enqueue(l); Ended=true; }); t.IsBackground=true; t.Start(); }
}
"@
$instances=@();$counter=0;$next=[datetime]::MinValue;$quit=$false
[QuotaInput]::Start()
while(-not $quit) {
 $line=$null
 while([QuotaInput]::Lines.TryDequeue([ref]$line)) {
  try {
   $m=$line|ConvertFrom-Json
   switch($m.type) {
    'initialize' {$instances=@($m.instances);$next=[datetime]::MinValue}
    'instancesChanged' {$instances=@($m.instances);$next=[datetime]::MinValue}
    'shutdown' {$quit=$true}
   }
  } catch {}
 }
 if([QuotaInput]::Ended -and $instances.Count -eq 0) {break}
 if([datetime]::UtcNow -ge $next -and -not $quit) {
  $data=@{label='QuotaBoard';quota='请启动 QuotaBoard';color='#FF666666';status='等待额度快照';icon=(Join-Path $PSScriptRoot 'assets/openai.png')}
  0..10|ForEach-Object {$data[('line'+$_)]=''}
  try {
   $path=Join-Path $env:APPDATA 'QuotaBoard/taskbar-snapshot.json'
   $snapshot=Get-Content -LiteralPath $path -Raw -Encoding UTF8|ConvertFrom-Json
   $items=@($snapshot.items)
   if($items.Count -gt 0) {
    $item=$items[([int][math]::Floor($counter/5)%$items.Count)]
    $data.label=[string]$item.label;$data.quota=[string]$item.display
    $names=@{codex='openai';chatgpt_plus='openai';zhipu_member='zhipu'}
    $name=[string]$item.platform;if($names.ContainsKey($name)){$name=$names[$name]}
    $icon=Join-Path $PSScriptRoot ('assets/'+$name+'.png');if(Test-Path -LiteralPath $icon){$data.icon=$icon}
    if(-not $item.ok){$data.color='#FFE45D6A'}elseif($null -ne $item.percent){$p=[double]$item.percent;$data.color=if($p -lt 30){'#FFE45D6A'}elseif($p -lt 75){'#FFE5A132'}else{'#FF27AE80'}}
    for($i=0;$i -lt [math]::Min(11,$items.Count);$i++) {$data['line'+$i]=[string]$items[$i].label+'  '+[string]$items[$i].display+'  '+[string]$items[$i].updated_at}
    $age=[datetime]::UtcNow-([datetime]$snapshot.updated_at).ToUniversalTime()
    $data.status=if($age.TotalMinutes -gt 5){'快照超过5分钟未更新，请检查 QuotaBoard'}else{'本机额度快照 · 每5秒轮换AI'}
    if($age.TotalMinutes -gt 5){$data.label+=' · 缓存'}
   }
  } catch {$data.status='无法读取快照，请启动新版 QuotaBoard'}
  foreach($instance in $instances) {
   @{type='snapshot';instanceId=[string]$instance.instanceId;status='ok';data=$data}|ConvertTo-Json -Compress -Depth 8|ForEach-Object {[Console]::WriteLine($_);[Console]::Out.Flush()}
  }
  $counter++;$next=[datetime]::UtcNow.AddSeconds(1)
 }
 if([QuotaInput]::Ended){break}
 Start-Sleep -Milliseconds 100
}
