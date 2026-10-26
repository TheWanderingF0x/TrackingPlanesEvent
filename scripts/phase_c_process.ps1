# Phase C PC brain wrapper
# Usage:
#   .\scripts\phase_c_process.ps1
#   .\scripts\phase_c_process.ps1 -Databricks
#   .\scripts\phase_c_process.ps1 -ExportOnly

param(
    [switch] $Databricks,
    [switch] $ExportOnly,
    [switch] $Weather,
    [string[]] $Date = @()
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$argv = @("scripts\phase_c_process.py")
if ($ExportOnly) { $argv += "--export-only" }
if ($Databricks) { $argv += "--databricks" }
if ($Weather) { $argv += "--weather" }
foreach ($d in $Date) { $argv += @("--date", $d) }

Write-Host "Running: $py $($argv -join ' ')"
& $py @argv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
