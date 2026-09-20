$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$outputRoot = Join-Path $projectRoot 'Student Os'
$workRoot = Join-Path $outputRoot 'build'
$appRoot = Join-Path $outputRoot 'Student Life OS'

$runningProcess = Get-Process -Name 'StudentLifeOS' -ErrorAction SilentlyContinue
if ($runningProcess) {
    $runningProcess | Stop-Process -Force
}

if (Test-Path $outputRoot) {
    Remove-Item $outputRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
python -m PyInstaller --noconfirm --clean --distpath $outputRoot --workpath $workRoot StudentLifeOS.spec

$finalExe = Join-Path $appRoot 'StudentLifeOS.exe'

if (-not (Test-Path $finalExe)) {
    throw "PyInstaller EXE olusturamadi: $finalExe"
}

$sourceResources = Join-Path $projectRoot 'resources'
$outputResources = Join-Path $appRoot 'resources'
if (-not (Test-Path $sourceResources)) {
    throw "resources klasoru bulunamadi: $sourceResources"
}
Copy-Item $sourceResources $outputResources -Recurse -Force

if (Test-Path $workRoot) {
    Remove-Item $workRoot -Recurse -Force
}

Start-Process -FilePath $finalExe -WorkingDirectory $appRoot
Write-Output "Uygulama hazirlandi ve baslatildi: $finalExe"