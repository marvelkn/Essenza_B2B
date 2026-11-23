param(
    [string]$Serial,
    [string]$ApiUrl = 'http://127.0.0.1:8000',
    [ValidatePattern('^[D-Z]$')][string]$DriveLetter = 'X',
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr' }
$adb = Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $adb) -or -not (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin\java.exe'))) {
    throw 'Atur ANDROID_HOME ke Android SDK dan JAVA_HOME ke JDK 17/21 terlebih dahulu.'
}
$env:Path = (Join-Path $env:JAVA_HOME 'bin') + ';' + $env:Path
$devices = @(& $adb devices | Select-String '^([^\s]+)\s+device$' | ForEach-Object { $_.Matches[0].Groups[1].Value })
if (-not $Serial) {
    if ($devices.Count -ne 1) { throw 'Sambungkan satu HP, aktifkan USB debugging, dan izinkan akses; atau isi -Serial.' }
    $Serial = $devices[0]
}
if ($Serial -notin $devices) { throw "HP $Serial belum berstatus device/authorized." }
$uri = [Uri]$ApiUrl
if ($uri.Host -in @('127.0.0.1','localhost')) {
    & $adb -s $Serial reverse "tcp:$($uri.Port)" "tcp:$($uri.Port)"
    if ($LASTEXITCODE -ne 0) { throw 'Gagal mengaktifkan koneksi USB ke API.' }
}
try {
    $health = Invoke-RestMethod -Uri ($ApiUrl.TrimEnd('/') + '/health') -TimeoutSec 10
    $manifest = Get-Content -LiteralPath (Join-Path $repo 'src\assets\metadata\v7_model_manifest.json') -Raw | ConvertFrom-Json
    if ($health.status -ne 'ok' -or $health.runtime -ne 'lightgbm' -or
        -not $health.model_ready -or -not $health.capabilities.local_prediction -or
        $health.model_id -ne $manifest.model_id -or $health.label_count -ne 109 -or
        $health.input_dimensions -ne 2056 -or $health.bundle_id -ne $manifest.bundle_id -or
        $health.feature_schema_id -ne $manifest.feature_schema_id) {
        throw 'Kontrak layanan berbeda dari paket model.'
    }
} catch { throw "API belum siap. Jalankan scripts/start-local-api.ps1 di terminal lain. $($_.Exception.Message)" }
$apk = Join-Path $repo 'android\app\build\outputs\apk\local\app-local.apk'
if (-not $SkipBuild) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo 'node_modules\react-native'))) {
        Push-Location -LiteralPath $repo
        try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'npm ci gagal.' } } finally { Pop-Location }
    }
    $drive = $DriveLetter.ToUpper() + ':'
    $existing = @(& subst.exe) | Where-Object { $_.StartsWith($drive, [StringComparison]::OrdinalIgnoreCase) }
    if ($existing) {
        $mapped = ($existing -split '=>', 2)[1].Trim()
        if ($mapped.TrimEnd('\') -ne $repo.TrimEnd('\')) { throw "$drive dipakai untuk $mapped. Gunakan -DriveLetter lain." }
    } else {
        if (Test-Path -LiteralPath ($drive + '\')) { throw "$drive sudah dipakai drive fisik. Pilih -DriveLetter lain." }
        & subst.exe $drive $repo
        if ($LASTEXITCODE -ne 0) { throw 'Gagal membuat path pendek build.' }
    }
    $runDir = Join-Path $repo '.local-run'
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    $marker = Join-Path $runDir 'android-build-root.txt'
    $buildRoot = $repo + '|' + $drive
    if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $buildRoot) {
        # Generated CMake/autolink paths become invalid when the checkout moves.
        $generated = @('android\build','android\app\build','android\app\.cxx','android\.gradle')
        foreach ($module in @('@react-native-async-storage\async-storage','react-native-screens','react-native-safe-area-context','react-native-svg','react-native-linear-gradient')) {
            $generated += "node_modules\$module\android\build"
            $generated += "node_modules\$module\android\.cxx"
        }
        foreach ($relative in $generated) {
            $target = [IO.Path]::GetFullPath((Join-Path $repo $relative))
            if (-not $target.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe cache path' }
            if (Test-Path -LiteralPath $target) {
                if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Unexpected linked cache: $target" }
                Remove-Item -LiteralPath $target -Recurse -Force
            }
        }
        Set-Content -LiteralPath $marker -Value $buildRoot
    }
    $abi = (& $adb -s $Serial shell getprop ro.product.cpu.abi).Trim()
    if ($abi -notin @('arm64-v8a','armeabi-v7a','x86','x86_64')) { throw "ABI HP tidak didukung: $abi" }
    Push-Location -LiteralPath ($drive + '\android')
    try {
        & .\gradlew.bat :app:assembleLocal "-PreactNativeArchitectures=$abi" "-PessenzaProjectRoot=$repo" --console=plain --max-workers=2 2>&1 | Tee-Object -FilePath (Join-Path $runDir 'android-build.log')
        if ($LASTEXITCODE -ne 0) { throw 'Build Android gagal.' }
    } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath $apk)) { throw 'APK lokal belum tersedia. Jalankan tanpa -SkipBuild.' }
& $adb -s $Serial install -r $apk
if ($LASTEXITCODE -ne 0) { throw 'Instalasi APK gagal. Data lama tidak dihapus; periksa pesan signature/storage.' }
& $adb -s $Serial shell am force-stop com.essenza.lab
& $adb -s $Serial shell am start -n com.essenza.lab/com.essenza.app.MainActivity
if ($LASTEXITCODE -ne 0) { throw 'Aplikasi belum berhasil dibuka.' }
Write-Output "Essenza lokal terpasang. APK: $apk"
Write-Output 'Build lokal tidak memerlukan Metro. USB harus tersambung untuk prediksi baru; riwayat/koleksi tersedia lokal.'
if ($uri.Host -notin @('127.0.0.1','localhost') -or $uri.Port -ne 8000) {
    Write-Output "Atur alamat $ApiUrl melalui Panduan -> Pengaturan koneksi pada HP. URL bawaan APK selalu http://127.0.0.1:8000."
}
