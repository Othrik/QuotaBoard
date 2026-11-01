# Run from the repository root after installing requirements in a dedicated venv.
$ErrorActionPreference = 'Stop'
$python = (Get-Command python -ErrorAction Stop).Source
# Prevent unrelated applications from supplying same-name Qt/ICU DLLs.
$originalPath = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    & $python -m PyInstaller --noconfirm --workpath build-isolated QuotaBoard.spec
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
} finally {
    $env:PATH = $originalPath
}
