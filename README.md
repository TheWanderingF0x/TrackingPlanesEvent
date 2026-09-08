# TrackingPlanesEvent

Live-collect [OpenSky Network](https://opensky-network.org/) state vectors for **major European airlines**, store timed snapshots, then use **PySpark** to reconstruct UTC-day flights (altitude and speed along the route). Explore results in **Streamlit** by company and aircraft type.

Built as a **learning project**: Python collector → Parquet lake → PySpark structuring → simple dashboard. Safe to open-source if you keep secrets out of git ([SECURITY.md](SECURITY.md)).

## Documentation

| Guide | Contents |
|-------|----------|
| **[docs/SETUP.md](docs/SETUP.md)** | Full setup: **local (Windows/Linux)** and **Oracle Always Free 24/7** |
| [deploy/oracle/README.md](deploy/oracle/README.md) | Short Oracle ops cheat sheet |
| [SECURITY.md](SECURITY.md) | Secrets policy for public GitHub |

## Quick start (local)

1. Get OpenSky **OAuth2** `client_id` / `client_secret` ([auth docs](https://openskynetwork.github.io/opensky-api/rest.html#authentication)).
2. Follow **[docs/SETUP.md](docs/SETUP.md)** §3–5 (venv, `.env`, Java, collector → Spark → Streamlit).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env — never commit it
python scripts/setup_hadoop_winutils.py
python scripts/run_collector.py
```

## Quick start (Oracle 24/7)

Create an Always Free **A1.Flex** VM (2 OCPU / 12 GB, Ubuntu 22.04), copy the project to `/opt/tracking-planes`, add `.env`, then:

```bash
sudo bash deploy/oracle/setup.sh
```

Full steps: **[docs/SETUP.md](docs/SETUP.md#6-oracle-cloud-always-free-247)**.

## Layout

| Path | Role |
|------|------|
| `docs/SETUP.md` | Local + Oracle setup guide |
| `.env` / `.env.example` | Secrets (local only) / placeholders |
| `config/airlines_europe.yaml` | Major EU airline ICAO prefixes |
| `src/tracking_planes/` | Auth, collector, Spark, Streamlit |
| `deploy/oracle/` | systemd + cron bootstrap for Always Free |
| `scripts/` | Run collector, Spark, secret check |

## License

MIT — see [LICENSE](LICENSE).
