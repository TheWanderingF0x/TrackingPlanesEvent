# Oracle Always Free — ops cheat sheet

Full walkthrough (create VM, copy files, Streamlit tunnel, troubleshooting):

→ **[docs/SETUP.md — §6 Oracle Cloud](../../docs/SETUP.md#6-oracle-cloud-always-free-247)**

## Shape

- Image: Ubuntu 22.04 aarch64
- Shape: `VM.Standard.A1.Flex` — **2 OCPU / 12 GB RAM** / 50 GB boot
- Firewall: SSH **22** only (not 8501)

## Install

```bash
# project at /opt/tracking-planes with .env already filled (chmod 600)
sudo timedatectl set-timezone UTC
cd /opt/tracking-planes
sudo bash deploy/oracle/setup.sh
```

## Verify

```bash
sudo systemctl status tracking-planes-collector
sudo journalctl -u tracking-planes-collector -f
sudo -u planes bash -lc 'cd /opt/tracking-planes && .venv/bin/python scripts/run_spark_yesterday.py'
```

## Streamlit (SSH tunnel)

```bash
# on VM
sudo -u planes bash -lc 'cd /opt/tracking-planes && .venv/bin/streamlit run src/tracking_planes/app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501'

# on PC
ssh -i ~/.ssh/your_key -L 8501:127.0.0.1:8501 ubuntu@<PUBLIC_IP>
# open http://127.0.0.1:8501
```

## Cron (installed by setup.sh)

- `15 0 * * *` — PySpark for previous UTC day
- Sunday prune — raw >14 days, curated >90 days

## Secrets

Never commit `.env`. Placeholders only in `.env.example`. See [SECURITY.md](../../SECURITY.md).
