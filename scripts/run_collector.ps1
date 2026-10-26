# Single trigger: multi-API collector (OpenSky + adsb.lol + callsign OD)
# Usage:
#   .\scripts\run_collector.ps1
#   .\scripts\run_collector.ps1 -Once
#   .\scripts\run_collector.ps1 -OpenSkyOnly
param(
    [switch]$Once,
    [switch]$OpenSkyOnly,
    [switch]$NoAdsb,
    [switch]$NoCallsignOd
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$argsList = @()
if ($Once) { $argsList += "--once" }
if ($OpenSkyOnly) { $argsList += "--opensky-only" }
if ($NoAdsb) { $argsList += "--no-adsb" }
if ($NoCallsignOd) { $argsList += "--no-callsign-od" }

Write-Host "Tracking Planes collector → data/raw (states + adsb_lol + callsign_routes)"
python scripts/run_collector.py @argsList
