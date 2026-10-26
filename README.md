# TrackingPlanesEvent

Live-collect [OpenSky Network](https://opensky-network.org/) state vectors for **major European airlines**, reconstruct UTC-day flights with **PySpark**, enrich with aircraft type / OD airports / specs, estimate **fuel & NOx** (Open-Meteo + scikit-learn), and publish results on a **modern React** site. **Databricks** lakehouse sync. Deploy in **two phases**: PC + Databricks first, then optional VPS/home server.

Built as a learning / portfolio project. Keep secrets out of git ([SECURITY.md](SECURITY.md)).

```text
Phase 1:  OpenSky → PC → Parquet → FastAPI/React → Databricks
Phase C:  Phone collect → Syncthing → PC brain → Vercel static + Databricks
Phase 2:  optional always-on VPS/home server
```

## Documentation

| Guide | Contents |
|-------|----------|
| **[docs/CLOUD_AND_DATABRICKS.md](docs/CLOUD_AND_DATABRICKS.md)** | Phase 1 / C / 2 deploy |
| **[docs/PHASE_C_PHONE.md](docs/PHASE_C_PHONE.md)** | Phone + Syncthing + Vercel static site |
| **[docs/SETUP.md](docs/SETUP.md)** | Local PC setup + Oracle/VPS host install |
| **[docs/DATABRICKS.md](docs/DATABRICKS.md)** | Volume sync, bronze/silver/gold |
| **[docs/EMISSIONS.md](docs/EMISSIONS.md)** | ICEC-inspired fuel / CO₂ / NOx estimates |
| **[docs/PM_PLAN_TrackingPlanesEvent.md](docs/PM_PLAN_TrackingPlanesEvent.md)** | Phased roadmap |
| [deploy/oracle/README.md](deploy/oracle/README.md) | Linux host ops (Oracle/VPS/server) |
| [deploy/phase2/README.md](deploy/phase2/README.md) | Phase 2 host choice cheat sheet |
| [SECURITY.md](SECURITY.md) | Secrets policy |

## Quick start — results website (sample data)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/generate_sample_results.py
python scripts/run_api.py
```

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173 — flights, route map, specs gaps, emissions totals.

## Quick start — live collect

1. OpenSky OAuth2 `client_id` / `client_secret` → `.env` (from `.env.example`).
2. Follow **[docs/SETUP.md](docs/SETUP.md)** §3–5 (collector → Spark → emissions → site).
3. Phase 1 check + Databricks sync:

```powershell
.\scripts\phase1_status.ps1
.\scripts\sync_to_databricks.ps1   # after databricks auth login
```

Full Phase 1/2: **[docs/CLOUD_AND_DATABRICKS.md](docs/CLOUD_AND_DATABRICKS.md)**.

## Interview bullets

1. **Credit-aware OpenSky polling** → Parquet lake → PySpark flight sessionization (gap / callsign / landing breaks).
2. **Honest enrichment:** nearest-airport OD, `aircraft_specs.is_complete` for analysis filters, manufacturer family from ICAO typecodes.
3. **Estimates, not certificates:** physics-inspired fuel/NOx proxies + sklearn, weather from free Open-Meteo; React+FastAPI as the public face, Streamlit for internal debug.

## Layout

| Path | Role |
|------|------|
| `src/tracking_planes/` | Auth, collector, Spark, weather, ML, FastAPI, Streamlit |
| `web/` | Vite + React results portal |
| `config/` | Airlines, airports, aircraft specs |
| `data/sample/` | Demo Parquet for the website |
| `deploy/oracle/` | systemd collector + API, nginx, cron (any Linux host) |
| `deploy/phase2/` | When to move off the PC |
| `scripts/phase1_status.ps1` | Phase 1 readiness check |
| `scripts/phase_c_process.py` | Phase C: Spark → emissions → static JSON (+ Databricks) |
| `scripts/phase_c_publish.ps1` | Phase C: process + push `web/public/data` → Vercel via GitHub |
| `scripts/sync_to_databricks.ps1` | Parquet → Databricks Volume |
| `docs/notebooks/` | Databricks bronze/silver/gold skeletons |

## License

MIT — see [LICENSE](LICENSE).
