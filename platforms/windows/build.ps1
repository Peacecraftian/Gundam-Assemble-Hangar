param([string]$Python = "")
& (Join-Path $PSScriptRoot '../../build.ps1') -Python $Python -OutputDirectory (Join-Path $PSScriptRoot 'dist')
