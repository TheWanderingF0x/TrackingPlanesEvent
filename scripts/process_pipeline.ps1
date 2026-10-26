# Pair raw lakes → Spark → emissions → static JSON (+ optional Databricks).
# Usage:
#   .\scripts\process_pipeline.ps1
#   .\scripts\process_pipeline.ps1 -Databricks
#   .\scripts\process_pipeline.ps1 -ExportOnly

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

$argv = @("scripts\process_pipeline.py")
if ($ExportOnly) { $argv += "--export-only" }
if ($Databricks) { $argv += "--databricks" }
if ($Weather) { $argv += "--weather" }
foreach ($d in $Date) { $argv += @("--date", $d) }

Write-Host "Running: $py $($argv -join ' ')"
& $py @argv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
