$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$outputRoot = Join-Path $projectRoot 'Student Os'
$workRoot = Join-Path $outputRoot 'build'

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Student Life OS - EXE Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python bulunamadi. Python PATH'e eklenmis olmali."
}

Write-Host "`n>>> Python:" -ForegroundColor Yellow
python --version

# Check PyInstaller
python -c "import PyInstaller; print('PyInstaller:', PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller kurulu degil. 'python -m pip install pyinstaller' calistir."
}

# Check required project files
foreach ($file in @('app.py', 'StudentLifeOS.spec')) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $file))) {
        throw "$file bulunamadi: $projectRoot"
    }
}

Write-Host "`n>>> Eski build temizleniyor..." -ForegroundColor Cyan

$runningProcess = Get-Process -Name 'StudentLifeOS' -ErrorAction SilentlyContinue
if ($runningProcess) {
    $runningProcess | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

if (Test-Path -LiteralPath $outputRoot) {
    Remove-Item -LiteralPath $outputRoot -Recurse -Force
}

$distRoot = $outputRoot
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null

Write-Host "`n>>> PyInstaller derlemesi basliyor..." -ForegroundColor Yellow
Write-Host ">>> Hata olursa GERCEK PyInstaller hatasi asagida gorunecek.`n" -ForegroundColor DarkYellow

$env:PYTHONIOENCODING = "utf-8"

python -m PyInstaller `
    --noconfirm `
    --clean `
    --log-level=INFO `
    --distpath "$distRoot" `
    --workpath "$workRoot" `
    "$projectRoot\StudentLifeOS.spec"

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[HATA] PyInstaller basarisiz oldu." -ForegroundColor Red
    Write-Host "Yukaridaki PyInstaller cikisinda asil hata gorunmelidir." -ForegroundColor Red
    exit $LASTEXITCODE
}

$finalRoot = Join-Path $distRoot 'Student Life OS'
$finalExe = Join-Path $finalRoot 'StudentLifeOS.exe'

if (-not (Test-Path -LiteralPath $finalExe)) {
    Write-Host "`n[HATA] Build tamamlandi ancak EXE bulunamadi:" -ForegroundColor Red
    Write-Host $finalExe -ForegroundColor Red
    exit 1
}

Write-Host "`n>>> Harici kaynaklar kopyalaniyor..." -ForegroundColor Cyan

$sourceResources = Join-Path $projectRoot 'resources'
$outputResources = Join-Path $finalRoot 'resources'

# The spec already bundles resources. This copy preserves the external/editable
# resources folder too, if the project needs files to remain writable.
if (Test-Path -LiteralPath $sourceResources) {
    if (-not (Test-Path -LiteralPath $outputResources)) {
        Copy-Item -LiteralPath $sourceResources -Destination $outputResources -Recurse -Force
    }
}

$vaultDir = Join-Path $finalRoot 'vault_storage'
$coversDir = Join-Path $outputResources 'covers'
$musicsDir = Join-Path $outputResources 'musics'

New-Item -ItemType Directory -Path $vaultDir -Force | Out-Null
New-Item -ItemType Directory -Path $coversDir -Force | Out-Null
New-Item -ItemType Directory -Path $musicsDir -Force | Out-Null

# Keep final package clean.
if (Test-Path -LiteralPath $workRoot) {
    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " BUILD BASARILI" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "EXE: $finalExe" -ForegroundColor Green
Write-Host ""

$answer = Read-Host "Uygulamayi simdi baslatmak ister misin? (E/H)"
if ($answer -match '^[EeYy]') {
    Start-Process -FilePath $finalExe -WorkingDirectory $finalRoot
}
