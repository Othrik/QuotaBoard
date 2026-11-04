param(
    [string]$BuildTools = 'C:\BuildTools\QuotaBoard',
    [string]$Dotnet = '',
    [string]$Source = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$local = Join-Path $repo '.tools/local-build'
if (-not $Dotnet) { $Dotnet = Join-Path $local 'dotnet/dotnet.exe' }
if (-not $Source) { $Source = Join-Path $local 'host' }
$vsdev = Join-Path $BuildTools 'Common7/Tools/VsDevCmd.bat'
foreach ($file in @($vsdev, $Dotnet, (Join-Path $Source 'src/native/CMakeLists.txt'))) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing local build prerequisite: $file" }
}
# Import the official toolchain environment without printing environment values.
$compilerEnvironment = & cmd.exe /d /c ('"'+$vsdev+'" -arch=x64 -host_arch=x64 >nul && set')
if ($LASTEXITCODE) { throw 'MSVC environment setup failed' }
foreach ($entry in $compilerEnvironment) {
    $pair = $entry -split '=', 2
    if ($pair.Count -eq 2 -and $pair[0]) { [Environment]::SetEnvironmentVariable($pair[0], $pair[1], 'Process') }
}
$env:DOTNET_CLI_HOME = Join-Path $local 'dotnet-home'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$native = Join-Path $local 'native-build'
& (Join-Path $Source 'build/generate-widget-catalog.ps1')
New-Item -ItemType Directory -Force (Join-Path $native 'Release') | Out-Null
$release = Join-Path $native 'Release'
& cl.exe /nologo /std:c++latest /EHsc /MD /O2 /utf-8 /LD /DUNICODE /D_UNICODE /DNOMINMAX /DWINVER=0x0A00 /D_WIN32_WINNT=0x0A00 /D_WIN32_IE=0x0A00 ("/Fo"+(Join-Path $release 'hook.obj')) ("/Fe"+(Join-Path $release 'TaskbarWidgets.Hook.dll')) (Join-Path $Source 'src/native/taskbar-hook/taskbar_widgets_hook.cpp') /link ole32.lib oleaut32.lib runtimeobject.lib gdi32.lib gdiplus.lib uiautomationcore.lib shcore.lib user32.lib shell32.lib advapi32.lib uuid.lib
if ($LASTEXITCODE) { throw 'Native build failed' }
& cl.exe /nologo /std:c++latest /EHsc /MD /O2 /utf-8 ("/I"+(Join-Path $Source 'src/native/taskbar-hook')) ("/Fo"+(Join-Path $release 'tests.obj')) ("/Fe"+(Join-Path $release 'TaskbarWidgetsNativeTests.exe')) (Join-Path $Source 'src/native/tests/layout_tests.cpp')
if ($LASTEXITCODE) { throw 'Native test build failed' }
& (Join-Path $release 'TaskbarWidgetsNativeTests.exe')
if ($LASTEXITCODE) { throw 'Native tests failed' }
$resources = Join-Path $Source 'src/loader/Resources'
New-Item -ItemType Directory -Force $resources | Out-Null
Copy-Item -LiteralPath (Join-Path $native 'Release/TaskbarWidgets.Hook.dll') -Destination $resources -Force
$publish = Join-Path $local 'publish'
& $Dotnet publish (Join-Path $Source 'src/loader/TaskbarWidgets.csproj') -c Release -r win-x64 --self-contained true -o $publish
if ($LASTEXITCODE) { throw 'Managed host build failed' }
$hostExe = Join-Path $publish 'QuotaBoard.TaskbarHost.exe'
if (-not (Test-Path -LiteralPath $hostExe)) { throw 'Taskbar host output missing' }
Copy-Item -LiteralPath $hostExe -Destination (Join-Path $repo 'assets/taskbar/QuotaBoard.TaskbarHost.exe') -Force
Write-Output 'Local taskbar build and native tests passed; bundled helper updated.'
