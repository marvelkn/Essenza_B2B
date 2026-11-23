param(
    [string]$PythonExe,
    [string]$SourceRun,
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [string]$BindAddress = '127.0.0.1',
    [switch]$AllowPubChem,
    [switch]$SetupOnly
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$venv = Join-Path $repo '.venv-feature-api'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $candidates = @($PythonExe,
        (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
        (Join-Path (Split-Path $repo -Parent) 'Perfume-MultiLabel-Classifier\.venv\Scripts\python.exe'))
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        $fromLauncher = & $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $candidates += $fromLauncher }
    }
    $base = $null
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $version = & $candidate -B -c 'import sys; print(str(sys.version_info.major) + "." + str(sys.version_info.minor))'
            if ($version -eq '3.12') { $base = $candidate; break }
        }
    }
    if (-not $base) { throw 'Python 3.12 diperlukan. Jalankan ulang dengan -PythonExe C:\path\python.exe.' }
    & $base -B -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Gagal membuat environment API.' }
}
$requirements = Join-Path $repo 'feature_api\requirements-dev.txt'
$stamp = Join-Path $venv 'requirements.sha256'
$digest = (Get-FileHash -LiteralPath $requirements).Hash + (Get-FileHash -LiteralPath (Join-Path $repo 'feature_api\requirements.txt')).Hash
if (-not (Test-Path -LiteralPath $stamp) -or (Get-Content -LiteralPath $stamp -Raw).Trim() -ne $digest) {
    & $python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Instalasi dependency API gagal.' }
    Set-Content -LiteralPath $stamp -Value $digest
}
$prepare = Join-Path $repo 'scripts\prepare-local-models.py'
if ($SourceRun) {
    & $python -B $prepare --source-run $SourceRun
} elseif (Test-Path -LiteralPath (Join-Path $repo 'feature_api\models\v7\label_000.joblib')) {
    & $python -B $prepare --verify-only
} else {
    & $python -B $prepare
}
if ($LASTEXITCODE -ne 0) { throw 'Model lokal belum siap. Periksa sumber v7 dan checksum pada pesan di atas.' }
if ($SetupOnly) { Write-Output "Environment dan 109 model lokal siap: $python"; return }
$env:ESSENZA_ALLOW_PUBCHEM = if ($AllowPubChem) { '1' } else { '0' }
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location -LiteralPath $repo
try {
    Write-Output "Analisis lokal RDKit + LightGBM asli: http://${BindAddress}:$Port; pencarian internet: $($AllowPubChem.IsPresent)"
    & $python -B -m uvicorn feature_api.app:app --host $BindAddress --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'API berhenti dengan error. Periksa pesan di atas dan port yang dipakai.' }
} finally { Pop-Location }
