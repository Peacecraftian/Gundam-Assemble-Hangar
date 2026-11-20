param([switch]$LaunchOnly)

$ErrorActionPreference = "Stop"
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA "Android/Sdk" }
$env:ANDROID_HOME = $sdk
$adb = Join-Path $sdk "platform-tools/adb.exe"
$emulator = Join-Path $sdk "emulator/emulator.exe"
$avdName = "Hangar_Landscape_Tablet"
$apk = Join-Path $PSScriptRoot "app/build/outputs/apk/debug/app-debug.apk"

function Find-Tablet {
    foreach ($device in (& $adb devices)) {
        if ($device -match "^(emulator-\d+)\s+device\s*$") {
            $serial = $Matches[1]
            if ((& $adb -s $serial emu avd name) -contains $avdName) { return $serial }
        }
    }
}

function Get-TabletProcess {
    Get-CimInstance Win32_Process -Filter "Name='emulator.exe' OR Name LIKE 'qemu-system%'" |
        Where-Object { $_.CommandLine -match '(?:^|\s)-avd\s+"?Hangar_Landscape_Tablet"?(?:\s|$)' }
}

$lock = [System.Threading.Mutex]::new($false, 'Local\GundamHangarTabletLauncher')
try {
    try { $ownsLock = $lock.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $ownsLock = $true }
    if (-not $ownsLock) { return }

    if (-not $LaunchOnly) {
        $config = Join-Path $PSScriptRoot ".gradle/config.properties"
        if (Test-Path $config) {
            $line = Get-Content $config | Where-Object { $_ -like "java.home=*" } | Select-Object -First 1
            if ($line) { $env:JAVA_HOME = $line.Substring(10) }
        }
        & (Join-Path $PSScriptRoot "gradlew.bat") -p $PSScriptRoot :app:assembleDebug
        if ($LASTEXITCODE) { throw "Android build failed." }
    }

    $serial = Find-Tablet
    $processes = @(Get-TabletProcess)
    if ($LaunchOnly -and ($processes | Where-Object { $_.CommandLine -match '(?:^|\s)-no-window(?:\s|$)' })) {
        $deadline = (Get-Date).AddMinutes(2)
        while (-not $serial) {
            if ((Get-Date) -gt $deadline) { throw "Could not connect to the hidden Hangar tablet." }
            Start-Sleep -Seconds 2
            $serial = Find-Tablet
        }
        & $adb -s $serial emu kill
        if ($LASTEXITCODE) { throw "Could not close the hidden Hangar tablet." }
        # Wait for the emulator to release the saved tablet before opening its window.
        foreach ($process in $processes) {
            if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) {
                Wait-Process -Id $process.ProcessId -Timeout 90 -ErrorAction SilentlyContinue
                if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) {
                    throw "The hidden Hangar tablet is still shutting down. Try the shortcut again shortly."
                }
            }
        }
        $serial = $null
        $processes = @()
    }

    if (-not $serial -and -not $processes.Count) {
        Start-Process -FilePath $emulator -ArgumentList @("-avd", $avdName) -WindowStyle Normal
    }
    $deadline = (Get-Date).AddMinutes(4)
    do {
        $serial = Find-Tablet
        if ($serial -and ((& $adb -s $serial shell getprop sys.boot_completed) -eq "1")) { break }
        if ((Get-Date) -gt $deadline) { throw "The Hangar tablet did not finish booting." }
        Start-Sleep -Seconds 2
    } while ($true)

    if (-not $LaunchOnly -or -not ((& $adb -s $serial shell pm path app.hangar.prototype) -match '^package:')) {
        if (-not (Test-Path -LiteralPath $apk)) { throw "The local Android APK is missing. Build it with run-tablet.ps1 first." }
        & $adb -s $serial install -r $apk
        if ($LASTEXITCODE) { throw "Tablet installation failed." }
    }
    & $adb -s $serial shell input keyevent KEYCODE_WAKEUP
    & $adb -s $serial shell wm dismiss-keyguard
    & $adb -s $serial shell am start -W -n app.hangar.prototype/.TabletActivity
    if ($LASTEXITCODE) { throw "Hangar Tablet could not be opened." }
    if ($LaunchOnly) {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($process in (Get-TabletProcess)) {
            if ($shell.AppActivate([int]$process.ProcessId)) { break }
        }
    }
} catch {
    if (-not $LaunchOnly) { throw }
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "Hangar Tablet")
    exit 1
} finally {
    if ($ownsLock) { $lock.ReleaseMutex() }
    $lock.Dispose()
}
