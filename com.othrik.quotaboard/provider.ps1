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

function Get-QuotaColor($percent) {
 if([double]$percent -lt 30){return '#FFE45D6A'}
 if([double]$percent -lt 75){return '#FFE5A132'}
 return '#FF27AE80'
}
function Set-QuotaParts($data,$item) {
 foreach($key in @('alert','head0','value0','separator','head1','value1','suffix')){$data[$key]=''}
 $data.headColor0='#FF17202B';$data.headColor1='#FF17202B';$data.valueColor0='#FF17202B';$data.valueColor1='#FF17202B'
 if(-not $item.ok){$data.alert='请求失败';$data.headColor0='#FFE45D6A';return}
 $metrics=@($item.metrics|Where-Object {$metricNumber=0.0;$null -ne $_.percent -and [double]::TryParse([string]$_.percent,[ref]$metricNumber)})
 foreach($m in $metrics){
  if($m.label -eq '周' -and [double]$m.percent -le 0){
   $notes=[string]$m.note+' '+[string]$item.sub_note
   $data.alert='周额度用完，等待重置'
   if($notes -match '周\s*重置\s*(?:\d{4}-)?(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}:\d{2}))?'){
    $clock=if($Matches[3]){' '+$Matches[3]}else{''}
    $data.alert=([int]$Matches[1]).ToString()+'月'+([int]$Matches[2]).ToString()+'日'+$clock+' 周重置'
   }
   $data.headColor0='#FFE45D6A';return
  }
 }
 if($metrics.Count -gt 0){
  for($i=0;$i -lt [math]::Min(2,$metrics.Count);$i++){
   $m=$metrics[$i];$label=[string]$m.label;$percent=[double]$m.percent
   $data['head'+$i]=$label+' '
   if($label -eq '5h' -and $percent -le 0){
    $notes=[string]$m.note+' '+[string]$item.sub_note
    $data['head'+$i]=if($notes -match '5h\s*重置\s*(\d{1,2}:\d{2})'){'5h '+$Matches[1]+'重置'}else{'5h 等待重置'}
    $data['value'+$i]=$data['head'+$i];$data['head'+$i]='';$data['valueColor'+$i]='#FFE45D6A'
   }else{$data['value'+$i]=('{0:F0}%' -f $percent);$data['valueColor'+$i]=Get-QuotaColor $percent}
  }
  if($metrics.Count -gt 1){$data.separator=' · '}
 }elseif($null -ne $item.percent -and [string]$item.display -match '^(.*?)(-?\d+(?:\.\d+)?%)(.*)$'){
  $data.head0=$Matches[1];$data.value0=$Matches[2];$data.suffix=$Matches[3];$data.valueColor0=Get-QuotaColor $item.percent
 }else{$data.head0=[string]$item.display}
}
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
  $data=@{label='QuotaBoard';quota='请启动 QuotaBoard';color='#FF666666';status='等待额度快照';icon=(Join-Path $PSScriptRoot 'assets/openai-transparent.png')}
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
    $icon=Join-Path $PSScriptRoot ('assets/'+$name+'-transparent.png');if(Test-Path -LiteralPath $icon){$data.icon=$icon}
    if(-not $item.ok){$data.color='#FFE45D6A'}elseif($null -ne $item.percent){$p=[double]$item.percent;$data.color=if($p -lt 30){'#FFE45D6A'}elseif($p -lt 75){'#FFE5A132'}else{'#FF27AE80'}}
    $details=@()
    if(-not $item.ok){$details+='查询状态：暂时无法获取'}
    elseif(@($item.metrics).Count -gt 0){
     foreach($metric in $item.metrics){
      if($null -eq $metric.percent){continue}
      $caption=if($metric.label -eq '5h'){'5 小时剩余'}elseif($metric.label -eq '周'){'每周剩余'}else{[string]$metric.label}
      $details+=$caption+'：'+('{0:F0}%' -f [double]$metric.percent)
      if($metric.note){$details+='重置时间：'+([string]$metric.note -replace '^(?:5h|周)\s*重置\s*','')}
     }
    }else{$details+='当前余额：'+[string]$item.display}
    $details+='刷新时间：'+[string]$item.updated_at
    for($i=0;$i -lt [math]::Min(11,$details.Count);$i++){$data['line'+$i]=$details[$i]}
    Set-QuotaParts $data $item
    $age=[datetime]::UtcNow-([datetime]$snapshot.updated_at).ToUniversalTime()
    $data.status=if($age.TotalMinutes -gt 5){'快照超过5分钟未更新，请检查 QuotaBoard'}else{'本机额度快照 · 每5秒轮换AI'}

   }
  } catch {$data.status='无法读取快照，请启动新版 QuotaBoard'}
  if(-not $data.ContainsKey('head0')){Set-QuotaParts $data ([pscustomobject]@{ok=$true;display=$data.quota;metrics=@();percent=$null})}
  foreach($instance in $instances) {
   @{type='snapshot';instanceId=[string]$instance.instanceId;status='ok';data=$data}|ConvertTo-Json -Compress -Depth 8|ForEach-Object {[Console]::WriteLine($_);[Console]::Out.Flush()}
  }
  $counter++;$next=[datetime]::UtcNow.AddSeconds(1)
 }
 if([QuotaInput]::Ended){break}
 Start-Sleep -Milliseconds 100
}
