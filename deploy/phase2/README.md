# Phase 2 — always-on host (VPS or home server)

Phase 1 keeps the stack on your **PC** and syncs Parquet to **Databricks**.  
When you want 24/7 without the laptop, pick **one** host below and reuse the Oracle Linux deploy scripts.

| Host | Notes |
|------|--------|
| Home server (e.g. Xeon 8 GB) | Best cost; Cloudflare Tunnel for public HTTPS |
| Hetzner / cheap VPS | ≥4 GB RAM, Ubuntu 22.04, public IPv4 |
| Oracle Always Free A1 | Free when capacity allows |

## Steps

1. Ubuntu 22.04 + SSH key  
2. From Windows PC:

```powershell
cd d:\Dev_Area\TrackingPlanesEvent
.\deploy\oracle\upload_from_windows.ps1 -PublicIp <IP> -User ubuntu
```

3. On the host: copy `.env`, then `sudo bash deploy/oracle/setup.sh`  
4. Sync to Databricks **from this host** (install CLI) or keep using `scripts/sync_to_databricks.ps1` after `rsync` of `data/`  

Day-to-day: [`docs/SETUP_AND_RUN.md`](../../docs/SETUP_AND_RUN.md).  
Archived notes: [`docs/archive/CLOUD_AND_DATABRICKS.md`](../../docs/archive/CLOUD_AND_DATABRICKS.md).  
Oracle-specific ops: [`../oracle/README.md`](../oracle/README.md).
