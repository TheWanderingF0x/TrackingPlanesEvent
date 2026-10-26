# Linux host ops — Oracle / VPS / home server

Day-to-day ops: **[docs/SETUP_AND_RUN.md](../../docs/SETUP_AND_RUN.md)**.  
Archived deep dives: [docs/archive/](../../docs/archive/) · [deploy/phase2/README.md](../phase2/README.md)

These systemd/nginx scripts work on any Ubuntu 22.04 host (not only OCI).

## Shape

- Image: Ubuntu 22.04 aarch64
- Shape: `VM.Standard.A1.Flex` — **2 OCPU / 12 GB RAM** / 50 GB boot
- Firewall: SSH **22**; HTTP **80** for React site. Do not expose Streamlit **8501**.

## Upload from Windows (PC → VM)

```powershell
cd d:\Dev_Area\TrackingPlanesEvent
.\deploy\oracle\upload_from_windows.ps1 -PublicIp <PUBLIC_IP>
```

Then SSH in, edit `.env`, run setup:

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<PUBLIC_IP>
cd /opt/tracking-planes
nano .env   # OPENSKY_CLIENT_ID / SECRET, SPARK_DRIVER_MEMORY=4g
chmod 600 .env
sudo timedatectl set-timezone UTC
sudo bash deploy/oracle/setup.sh
```

`setup.sh` installs: collector, FastAPI, nginx + React build, Spark + emissions cron, sample data so the site works immediately.

## Verify

```bash
sudo systemctl status tracking-planes-collector tracking-planes-api nginx
curl -s http://127.0.0.1:8000/api/health
curl -sI http://127.0.0.1/
```

Open `http://<PUBLIC_IP>/` (OCI Security List / NSG must allow **TCP 80**).

## Streamlit (internal, SSH tunnel)

```bash
sudo -u planes bash -lc 'cd /opt/tracking-planes && .venv/bin/streamlit run src/tracking_planes/app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501'
# PC: ssh -L 8501:127.0.0.1:8501 ubuntu@<IP>
```

## Cron (UTC)

| Time | Job |
|------|-----|
| 00:15 | PySpark previous day |
| 01:00 | Emissions (Open-Meteo + ML) |
| 01:10 | API cache reload |
| Sun 03:30/03:40 | Prune raw / curated |

## Secrets

Never commit `.env`. See [SECURITY.md](../../SECURITY.md).
