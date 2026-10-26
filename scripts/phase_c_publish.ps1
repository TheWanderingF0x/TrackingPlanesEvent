# Phase C: process lake + commit/push web/public/data so Vercel (GitHub) redeploys.
#
# Usage:
#   .\scripts\phase_c_publish.ps1
#   .\scripts\phase_c_publish.ps1 -ExportOnly
#   .\scripts\phase_c_publish.ps1 -Databricks
#   .\scripts\phase_c_publish.ps1 -SkipPush          # commit only
#   .\scripts\phase_c_publish.ps1 -Message "daily snapshot"

param(
    [switch] $Databricks,
    [switch] $ExportOnly,
    [switch] $Weather,
    [switch] $SkipPush,
    [string[]] $Date = @(),
    [string] $Message = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

# 1) Brain: Spark / emissions / static JSON
$procArgs = @{}
if ($Databricks) { $procArgs["Databricks"] = $true }
if ($ExportOnly) { $procArgs["ExportOnly"] = $true }
if ($Weather) { $procArgs["Weather"] = $true }
if ($Date.Count -gt 0) { $procArgs["Date"] = $Date }

Write-Host "=== phase_c_process ===" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "phase_c_process.ps1") @procArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$dataDir = "web/public/data"
if (-not (Test-Path $dataDir)) {
    Write-Error "Missing $dataDir after process — abort publish."
}

# 2) Stage only static site payload (never .env / secrets)
git add -- $dataDir
$status = git status --porcelain -- $dataDir
if (-not $status) {
    Write-Host "No changes under $dataDir — nothing to commit. Vercel already has latest data." -ForegroundColor Yellow
    exit 0
}

Write-Host "=== git commit ===" -ForegroundColor Cyan
Write-Host $status
$ts = Get-Date -Format "yyyy-MM-dd HH:mm"
if (-not $Message) {
    $Message = "chore: refresh Vercel static data snapshot ($ts)"
}

git commit -m $Message
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($SkipPush) {
    Write-Host "Committed locally. Skipped push (-SkipPush). Push when ready: git push" -ForegroundColor Yellow
    exit 0
}

Write-Host "=== git push ===" -ForegroundColor Cyan
git push
if ($LASTEXITCODE -ne 0) {
    Write-Error "git push failed. Fix remote/auth, then: git push"
}

Write-Host ""
Write-Host "Done. Vercel will rebuild from GitHub (rootDirectory=web)." -ForegroundColor Green
