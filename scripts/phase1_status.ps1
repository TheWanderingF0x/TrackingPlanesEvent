# Phase 1 readiness check: PC stack + optional Databricks CLI.
# Usage: .\scripts\phase1_status.ps1

$ErrorActionPreference = "Continue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Ok([string] $msg) { Write-Host "  [OK]  $msg" -ForegroundColor Green }
function Bad([string] $msg) { Write-Host "  [!!]  $msg" -ForegroundColor Yellow }
function Info([string] $msg) { Write-Host "  [--]  $msg" -ForegroundColor Gray }

Write-Host ""
Write-Host "=== Phase 1 status - TrackingPlanesEvent ===" -ForegroundColor Cyan
Write-Host "Root: $RepoRoot"
Write-Host ""

# Python / venv
if (Test-Path ".\.venv\Scripts\python.exe") {
    Ok "venv Python: .\.venv\Scripts\python.exe"
} else {
    Bad "No .venv - create with: python -m venv .venv ; then activate and pip install -r requirements.txt"
}

# .env
if (Test-Path ".\.env") {
    Ok ".env present (secrets stay local)"
    $envText = Get-Content ".\.env" -Raw
    if ($envText -match 'your_client_id_here' -or $envText -match 'OPENSKY_CLIENT_ID=\s*$') {
        Bad "OpenSky placeholders still in .env - fill real OAuth client"
    } elseif ($envText -match 'OPENSKY_CLIENT_ID=') {
        Ok "OPENSKY_CLIENT_ID set"
    } else {
        Bad "OPENSKY_CLIENT_ID missing from .env"
    }
} else {
    Bad "No .env - copy from .env.example and add OpenSky credentials"
}

# Data layers
$layers = @(
    @{ Name = "raw/states"; Path = "data\raw\states"; Hint = "run scripts/run_collector.py" },
    @{ Name = "silver/flights"; Path = "data\silver\flights"; Hint = "run scripts/run_spark_pipeline.py --date YYYY-MM-DD" },
    @{ Name = "gold/emissions"; Path = "data\gold\flight_emissions_estimates"; Hint = "run scripts/run_emissions.py" },
    @{ Name = "reference/specs"; Path = "data\reference"; Hint = "created by Spark pipeline" },
    @{ Name = "sample (demo)"; Path = "data\sample"; Hint = "optional: scripts/generate_sample_results.py" }
)
Write-Host ""
Write-Host "Data lake:"
foreach ($l in $layers) {
    $p = Join-Path $RepoRoot $l.Path
    if (Test-Path $p) {
        $n = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        Ok "$($l.Name) ($n files)"
    } else {
        Bad "$($l.Name) missing - $($l.Hint)"
    }
}

# Web
Write-Host ""
Write-Host "Web:"
if (Test-Path ".\web\package.json") {
    Ok "web/ present"
    if (Test-Path ".\web\node_modules") {
        Ok "node_modules installed"
    } else {
        Bad "run: cd web ; npm install"
    }
    if (Test-Path ".\web\dist") {
        Ok "web/dist build exists (for production static)"
    } else {
        Info "no web/dist yet - npm run build when you want static behind API/nginx"
    }
} else {
    Bad "web/ missing"
}

# API health (if running)
Write-Host ""
Write-Host "API:"
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2
    Ok "/api/health responded"
    if ($h.data_root) { Info "data_root = $($h.data_root)" }
} catch {
    Info "API not reachable on :8000 - start: python scripts/run_api.py"
}

# Databricks CLI
Write-Host ""
Write-Host "Databricks:"
$venvCli = Join-Path $RepoRoot ".venv\Scripts\databricks.exe"
$cli = Get-Command databricks -ErrorAction SilentlyContinue
if (Test-Path $venvCli) {
    Ok "databricks CLI (venv): $venvCli"
    Info "sync: .\scripts\sync_to_databricks.ps1"
    Info "auth: databricks configure   OR set DATABRICKS_HOST + DATABRICKS_TOKEN"
} elseif ($cli) {
    Ok "databricks CLI: $($cli.Source)"
    Info "sync: .\scripts\sync_to_databricks.ps1"
} else {
    Bad "CLI missing - pip install -r requirements.txt  (databricks-cli)"
}

if ($env:DATABRICKS_HOST) {
    Ok "DATABRICKS_HOST set"
} else {
    Info "DATABRICKS_HOST not set (optional if using auth login profile)"
}

Write-Host ""
Write-Host "Next: docs/CLOUD_AND_DATABRICKS.md (Phase 1 checklist)"
Write-Host ""
