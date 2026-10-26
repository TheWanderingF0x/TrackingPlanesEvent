# Sync local Parquet lake -> Databricks Volume (Phase 1).
# Uses scripts/sync_to_databricks.py + databricks-sdk (reads .env).
#
# Usage:
#   .\scripts\sync_to_databricks.ps1
#   .\scripts\sync_to_databricks.ps1 -WhatIf
#   .\scripts\sync_to_databricks.ps1 -Layers silver,gold,reference

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string] $Catalog = "",
    [string] $Schema = "",
    [string] $VolumeName = "",
    [string[]] $Layers = @("raw", "curated", "silver", "gold", "reference")
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "No .venv Python at $py - create venv and pip install -r requirements.txt"
}

$script = Join-Path $RepoRoot "scripts\sync_to_databricks.py"
$layerArg = ($Layers -join ",")
$argv = @($script, "--layers", $layerArg)
if ($Catalog) { $argv += @("--catalog", $Catalog) }
if ($Schema) { $argv += @("--schema", $Schema) }
if ($VolumeName) { $argv += @("--volume", $VolumeName) }
if ($WhatIfPreference) { $argv += "--dry-run" }

Write-Host "Running: $py $($argv -join ' ')"
& $py @argv
if ($LASTEXITCODE -ne 0) {
    Write-Error "sync_to_databricks.py failed (exit $LASTEXITCODE)"
}
