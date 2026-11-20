param([string]$DotNet = "", [switch]$SkipTests)

$ErrorActionPreference = "Stop"
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (Test-Path -LiteralPath (Join-Path $repo ".ARCHIVED-WORKSPACE")) { throw "Build from the active checkout." }
if (-not $DotNet) {
    $local = Join-Path $repo ".build/dotnet/dotnet.exe"
    $DotNet = if (Test-Path -LiteralPath $local) { $local } else { "dotnet" }
}
$DotNet = (Get-Command $DotNet -ErrorAction Stop).Source
$previousCliHome = $env:DOTNET_CLI_HOME
$previousTelemetry = $env:DOTNET_CLI_TELEMETRY_OPTOUT
$previousFirstRun = $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE
Push-Location -LiteralPath $repo
try {
    $env:DOTNET_CLI_HOME = Join-Path $repo ".build/dotnet-home"
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
    $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
    if (-not $SkipTests) {
        & $DotNet build launcher/tests/Hangar.Launcher.Tests.csproj -c Release --nologo
        if ($LASTEXITCODE -ne 0) { throw "Launcher tests did not build." }
        & $DotNet .build/launcher/bin/Hangar.Launcher.Tests/Release/net10.0/Hangar.Launcher.Tests.dll .build/launcher/tests
        if ($LASTEXITCODE -ne 0) { throw "Launcher tests failed." }
    }
    & $DotNet publish launcher/Hangar.Launcher.csproj -c Release -r win-x64 --self-contained true -o "dist/Hangar Terminal" --nologo
    if ($LASTEXITCODE -ne 0) { throw "Launcher publish failed." }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README.md") -Destination "dist/Hangar Terminal/README.md"
    # References are an explicit allowlist; no catalogs, matches, authoring files or full repository copy.
    $references = "dist/Hangar Terminal/References"
    New-Item -ItemType Directory -Force $references | Out-Null
    foreach ($name in @("GA_Official Core Rulebook_en_1106.pdf", "Gundam_Assemble_Website_Play_Guide.pdf", "Gundam-Assemble-Demo-Scenario.pdf")) {
        $source = Join-Path $repo "Rules/$name"
        if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $references }
        else { Write-Warning "Missing reference: $name. Configure its path before deployment." }
    }
    Write-Host "Portable launcher: $repo/dist/Hangar Terminal/Hangar.Launcher.exe"
    Write-Host "Source-checkout preview: & '$repo/dist/Hangar Terminal/Hangar.Launcher.exe' --config '$repo/launcher/launcher.development.json'"
}
finally {
    $env:DOTNET_CLI_HOME = $previousCliHome
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = $previousTelemetry
    $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = $previousFirstRun
    Pop-Location
}
