# Upload TrackingPlanesEvent to an Oracle Ubuntu VM (Windows PowerShell).
# Usage:
#   .\deploy\oracle\upload_from_windows.ps1 -PublicIp 1.2.3.4
#   .\deploy\oracle\upload_from_windows.ps1 -PublicIp 1.2.3.4 -KeyPath $env:USERPROFILE\.ssh\id_ed25519 -User ubuntu
#
# Does NOT copy .env (create it on the VM). Excludes .venv, node_modules, raw data.

param(
    [Parameter(Mandatory = $true)]
    [string]$PublicIp,

    [string]$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519",
    [string]$User = "ubuntu",
    [string]$RemoteDir = "/opt/tracking-planes",
    [switch]$RunSetup
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Stamp = Get-Date -Format "yyyyMMddHHmmss"
$Archive = Join-Path $env:TEMP "tracking-planes-$Stamp.tar.gz"

if (-not (Test-Path $KeyPath)) {
    throw "SSH key not found: $KeyPath"
}

Write-Host "==> Project: $ProjectRoot"
Write-Host "==> Archive: $Archive"
Write-Host "==> Target:  ${User}@${PublicIp}:${RemoteDir}"

Push-Location $ProjectRoot
try {
    # Windows tar (bsdtar) — exclude heavy / secret paths
    & tar -czf $Archive `
        --exclude=".venv" `
        --exclude="web/node_modules" `
        --exclude="web/dist" `
        --exclude=".git" `
        --exclude="data/raw" `
        --exclude="data/curated" `
        --exclude="data/silver" `
        --exclude="data/gold" `
        --exclude="data/aircraft" `
        --exclude="data/reference" `
        --exclude=".env" `
        --exclude="__pycache__" `
        --exclude="*.pyc" `
        --exclude="logs" `
        --exclude="metastore_db" `
        --exclude="spark-warehouse" `
        .
} finally {
    Pop-Location
}

$ssh = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=accept-new")
$remote = "${User}@${PublicIp}"

Write-Host "==> Creating remote directory"
& ssh @ssh $remote "sudo mkdir -p $RemoteDir && sudo chown ${User}:${User} $RemoteDir"

Write-Host "==> Uploading archive"
& scp @ssh $Archive "${remote}:/tmp/tracking-planes-upload.tar.gz"

Write-Host "==> Extracting on VM"
& ssh @ssh $remote @"
set -e
cd $RemoteDir
tar -xzf /tmp/tracking-planes-upload.tar.gz
rm -f /tmp/tracking-planes-upload.tar.gz
if [ ! -f .env ]; then
  cp .env.example .env
  echo 'CREATED .env from example — edit secrets before setup.sh'
fi
"@

Remove-Item -Force $Archive -ErrorAction SilentlyContinue
Write-Host "==> Upload complete."

if ($RunSetup) {
    Write-Host "==> Running setup.sh on VM (needs .env secrets filled first)"
    & ssh @ssh $remote "cd $RemoteDir && sudo bash deploy/oracle/setup.sh"
} else {
    Write-Host @"

Next on the VM:
  ssh -i $KeyPath $remote
  cd $RemoteDir
  nano .env   # set OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET / SPARK_DRIVER_MEMORY=4g
  chmod 600 .env
  sudo timedatectl set-timezone UTC
  sudo bash deploy/oracle/setup.sh

OCI firewall: allow TCP 22 and TCP 80 (Ingress on VCN + optionally ufw).
Site: http://${PublicIp}/
"@
}
