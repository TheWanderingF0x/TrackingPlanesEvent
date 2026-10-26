# Pair raw → Spark → emissions model → static JSON → optional Databricks →
# commit/push web/public/data so Vercel redeploys from GitHub.
#
# Usage:
#   .\scripts\process_and_publish.ps1
#   .\scripts\process_and_publish.ps1 -Databricks
#   .\scripts\process_and_publish.ps1 -ExportOnly
#   .\scripts\process_and_publish.ps1 -SkipPush
#   .\scripts\process_and_publish.ps1 -Message "daily snapshot"

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

$procArgs = @{}
if ($Databricks) { $procArgs["Databricks"] = $true }
if ($ExportOnly) { $procArgs["ExportOnly"] = $true }
if ($Weather) { $procArgs["Weather"] = $true }
if ($Date.Count -gt 0) { $procArgs["Date"] = $Date }

Write-Host "=== process_pipeline ===" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "process_pipeline.ps1") @procArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$dataDir = "web/public/data"
if (-not (Test-Path $dataDir)) {
    Write-Error "Missing $dataDir after process — abort publish."
}

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
